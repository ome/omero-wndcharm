#
#
from omero import scripts
import omero.model
from omero.rtypes import rstring, rlong
from datetime import datetime
from math import ceil
from itertools import izip

import sys, os
basedir = os.getenv('HOME') + '/work/omero-pychrm'
for p in ['/utils', '/pychrm-lib']:
    if basedir + p not in sys.path:
        sys.path.append(basedir + p)
import FeatureHandler
import pychrm.FeatureSet




def createWeights(tcIn, tcF, tcW, tcL, datasets, featureThreshold):
    # Build the classifier (basically a set of weights)
    message = ''
    trainFts = pychrm.FeatureSet.FeatureSet_Discrete()

    classId = 0
    for ds in datasets:
        message += 'Processing dataset id:%d\n' % ds.getId()
        message += addToFeatureSet(tcIn, ds, trainFts, classId)
        classId += 1

    tmp = trainFts.ContiguousDataMatrix()
    weights = pychrm.FeatureSet.FisherFeatureWeights.NewFromFeatureSet(trainFts)

    if featureThreshold < 1.0:
        nFeatures = ceil(len(weights.names) * featureThreshold)
        message += 'Selecting top %d features\n' % nFeatures
        weights = weights.Threshold(nFeatures)
        trainFts = reduceFeatures(trainFts, weights)


    # Save the features, weights and classes to tables
    # TODO:Delete existing tables
    # TODO:Attach to project as annotation
    #if getProjectTableFile(tcOutF, tcF.tableName, proj):
    FeatureHandler.createClassifierTables(tcF, tcW, tcL, weights.names)
    message += 'Created classifier tables\n'
    #message += addFileAnnotationToProject(tcOutF, tcF.table, proj)

    # We've (ab)used imagenames_list to hold the image ids
    ids = [long(a) for b in trainFts.imagenames_list for a in b]
    classIds = [a for b in [[i] * len(z) for i, z in izip(xrange(
                    len(trainFts.imagenames_list)), trainFts.imagenames_list)]
                for a in b]
    featureMatrix = trainFts.data_matrix
    featureNames = weights.names
    featureWeights = weights.values
    classNames = trainFts.classnames_list

    FeatureHandler.saveClassifierTables(
        tcF, tcW, tcL, ids, classIds, featureMatrix,
        featureNames, featureWeights, classNames)
    message += 'Saved classifier\n'
    return trainFts, weights, message


def reduceFeatures(fts, weights):
    if fts.source_path is None:
        fts.source_path = ''
    ftsr = fts.FeatureReduce(weights.names)
    return ftsr


def predictDataset(tcIn, trainFts, predDs, weights):
    message = ''
    predictFts = pychrm.FeatureSet.FeatureSet_Discrete()
    classId = 0
    message += addToFeatureSet(tcIn, predDs, predictFts, classId)
    tmp = predictFts.ContiguousDataMatrix()

    predictFts = reduceFeatures(predictFts, weights)

    pred = pychrm.FeatureSet.DiscreteBatchClassificationResult.New(
        trainFts, predictFts, weights)
    return pred, message


    #message = FeatureHandler.saveFeatures(tcOut, 0, weights)
    #return message + 'Saved classifier weights\n'


def formatPredResult(r):
    return 'ID:%s Prediction:%s Probabilities:[%s]' % \
        (r.source_file, r.predicted_class_name,
         ' '.join(['%.3e' % p for p in r.marginal_probabilities]))


def addPredictionsAsComments(tc, prediction, dsId, commentImages):
    """
    Add a comment to the dataset containing the prediction results.
    @param commentImages If true add comment to individual images as well
    as the dataset
    """
    dsComment = ''

    for r in prediction.individual_results:
        c = formatPredResult(r)
        imId = long(r.source_file)

        if commentImages:
            FeatureHandler.addCommentTo(tc, c, 'Image', imId)
        im = tc.conn.getObject('Image', imId)
        dsComment += im.getName() + ' ' + c + '\n'

    FeatureHandler.addCommentTo(tc, dsComment, 'Dataset', dsId)


def addToFeatureSet(tcIn, ds, fts, classId):
    message = ''

    tid = FeatureHandler.getAttachedTableFile(tcIn, tcIn.tableName, ds)
    if tid:
        if not FeatureHandler.openTable(tcIn, tableId=tid):
            return message + '\nERROR: Table not opened'
        message += 'Opened table id:%d\n' % tid
    else:
        message += 'ERROR: Table not found for Dataset id:%d' % ds.getId()
        return message

    #fts = pychrm.FeatureSet.FeatureSet_Discrete({'num_images': 0})
    for image in ds.listChildren():
        imId = image.getId()
        message += '\tProcessing features for image id:%d\n' % imId
        #message += extractFeatures(tc, d, im = image) + '\n'

        sig = pychrm.FeatureSet.Signatures()
        (sig.names, sig.values) = FeatureHandler.loadFeatures(tcIn, imId)
        #sig.source_file = image.getName()
        sig.source_file = str(imId)
        fts.AddSignature(sig, classId)

    fts.classnames_list[classId] = ds.getName()
    return message


def trainAndPredict(client, scriptParams):
    message = ''

    # for params with default values, we can get the value directly
    dataType = scriptParams['Data_Type']
    trainIds = scriptParams['Training_IDs']
    predictIds = scriptParams['Predict_IDs']
    commentImages = scriptParams['Comment_images']

    contextName = scriptParams['Context_Name']
    featureThreshold = scriptParams['Features_threshold'] / 100.0

    tableNameIn = '/Pychrm/' + contextName + FeatureHandler.SMALLFEATURES_TABLE
    tableNameOutF = '/Pychrm/' + contextName + \
        FeatureHandler.CLASS_WEIGHTS_TABLE
    tableNameOutW = '/Pychrm/' + contextName + \
        FeatureHandler.CLASS_FEATURES_TABLE
    tableNameOutL = '/Pychrm/' + contextName + \
        FeatureHandler.CLASS_LABELS_TABLE
    message += 'tableNameIn:' + tableNameIn + '\n'
    message += 'tableNameOutF:' + tableNameOutF + '\n'
    message += 'tableNameOutW:' + tableNameOutW + '\n'
    message += 'tableNameOutL:' + tableNameOutL + '\n'

    tcIn = FeatureHandler.connect(client, tableNameIn)
    tcOutF = FeatureHandler.connect(client, tableNameOutF)
    tcOutW = FeatureHandler.connect(client, tableNameOutW)
    tcOutL = FeatureHandler.connect(client, tableNameOutL)

    try:
        # Training
        message += 'Training classifier\n'
        trainDatasets = tcIn.conn.getObjects(dataType, trainIds)
        trainFts, weights, msg = createWeights(
            tcIn, tcOutF, tcOutW, tcOutL, trainDatasets, featureThreshold)
        message += msg

        # Predict
        #message += 'Predicting\n'
        #predDatasets = tcIn.conn.getObjects(dataType, predictIds)

        #for ds in predDatasets:
        #    message += 'Predicting dataset id:%d\n' % ds.getId()
        #    pred, msg = predictDataset(tcIn, trainFts, ds, weights)
        #    message += msg
        #    addPredictionsAsComments(tcOut, pred, ds.getId(), commentImages)

    except:
        print message
        raise
    finally:
        tcIn.closeTable()
        tcOutF.closeTable()
        tcOutW.closeTable()
        tcOutL.closeTable()

    return message


def runScript():
    """
    The main entry point of the script, as called by the client via the scripting service, passing the required parameters. 
    """

    client = scripts.client(
        'Pycharm_Build_Classifier.py',
        'Build a classifier from features calculated over two or more ' +
        'datasets, each dataset represents a different class',

        scripts.String('Data_Type', optional=False, grouping='1',
                       description='The data you want to work with.',
                       values=[rstring('Dataset')], default='Dataset'),

        scripts.List(
            'Training_IDs', optional=False, grouping='1',
            description='List of training Dataset IDs').ofType(rlong(0)),

        scripts.List(
            'Predict_IDs', optional=False, grouping='1',
            description='List of Dataset IDs to be predicted').ofType(rlong(0)),

        scripts.Bool(
            'Comment_images', optional=False, grouping='1',
            description='Add predictions as image comments', default=False),

        scripts.String(
            'Context_Name', optional=False, grouping='1',
            description='The name of the classification context.',
            default='Example'),

        scripts.Long(
            'Features_threshold', optional=False, grouping='2',
            description='The proportion of features to keep (%)\n' + \
                '(Should be a Double but doesn\'t seem to work)',
            default=100),

        version = '0.0.1',
        authors = ['Simon Li', 'OME Team'],
        institutions = ['University of Dundee'],
        contact = 'ome-users@lists.openmicroscopy.org.uk',
    )

    try:
        startTime = datetime.now()
        session = client.getSession()
        client.enableKeepAlive(60)
        scriptParams = {}

        # process the list of args above.
        for key in client.getInputKeys():
            if client.getInput(key):
                scriptParams[key] = client.getInput(key, unwrap=True)
        message = str(scriptParams) + '\n'

        # Run the script
        message += trainAndPredict(client, scriptParams) + '\n'

        stopTime = datetime.now()
        message += 'Duration: %s' % str(stopTime - startTime)

        print message
        client.setOutput('Message', rstring(message))

    finally:
        client.closeSession()

if __name__ == '__main__':
    runScript()

