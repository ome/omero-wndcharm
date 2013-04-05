#!/usr/bin/env python
# -*- coding: utf-8 -*-

#
# Copyright (C) 2013 University of Dundee & Open Microscopy Environment.
# All rights reserved.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

#
#

import xml.dom.minidom
try:
    from xml.etree.ElementTree import XML, Element, SubElement, Comment, ElementTree, tostring
except ImportError:
    from elementtree.ElementTree import XML, Element, SubElement, Comment, ElementTree, tostring


CLASSIFIER_NAMESPACE = 'openmicroscopy.org/omero/analysis/classifier'
ADDITIONS_NAMESPACE = 'http://www.openmicroscopy.org/Schemas/Additions/2011-09'
STRUCTUREDANNOTATIONS_NAMESPACE = "http://www.openmicroscopy.org/Schemas/SA/2012-06"

class InvalidXmlError(Exception):
    pass

class XmlError(Exception):
    pass

class Algorithm(object):
    def __init__(self, id, parameters):
        self.id = id
        self.parameters = parameters

class Image(object):
    def __init__(self, id, z, c, t):
        self.id = id
        self.z = z
        self.c = c
        self.t = t

class Prediction(object):
    def __init__(self, id, z, c, t, label):
        self.id = id
        self.z = z
        self.c = c
        self.t = t
        self.label = label

class FeatureSet(object):
    def __init__(self, algorithm, tableId, images):
        self.algorithm = algorithm
        self.tableId = tableId
        self.images = images

class ClassifierInstance(object):
    def __init__(self, algorithm, trainingIds, selectedId, weightsId, labels):
        self.algorithm = algorithm
        self.trainingIds = trainingIds
        self.selectedId = selectedId
        self.weightsId = weightsId
        self.labels = labels

class ClassifierPrediction(object):
    def __init__(self, algorithm, predictions):
        self.algorithm = algorithm
        self.predictions = predictions



class Reader(object):

    def __init__(self, xmlText=None, xmlFile=None):
        if xmlFile:
            if xmlText:
                raise Exception(
                    'Only one of xmlText or xmlFile should be provided')
            with open(xmlFile) as f:
                xmlText = f.read()

        self.xml = XML(xmlText)
        self.ns = self.getNs()

    def getNs(self):
        tag = self.xml.tag
        a = tag.find('{')
        b = tag.find('}')
        if a == -1:
            assert(b == -1)
            return None

        assert(a == 0 and b > 0)
        return tag[(a + 1):b]

    def preNs(self, tag):
        return '{%s}%s' % (self.ns, tag)

    def getFeatureSet(self, xml):
        """
        Look for FeatureSet elements
        @param xml The parent XML element in which to search
        """
        xs = xml.findall('.//' + self.preNs('FeatureSet'))
        fs = [self.parseFeatureSet(x) for x in xs]
        return fs

    def getClassifierInstance(self, xml):
        """
        Look for ClassifierInstance elements
        @param xml The parent XML element in which to search
        """
        xs = xml.findall('.//' + self.preNs('ClassifierInstance'))
        ci = [self.parseClassifierInstance(x) for x in xs]
        return ci

    def getClassifierPrediction(self, xml):
        """
        Look for ClassifierPrediction elements
        @param xml The parent XML element in which to search
        """
        xs = xml.findall('.//' + self.preNs('ClassifierPrediction'))
        cp = [self.parseClassifierPrediction(x) for x in xs]
        return cp


    def attribNotNone(self, xml, name, type=None):
        """
        Get an attribute from an element, raise an exception if not present
        @param xml The element
        @param name The name of the attribute
        @param type Optionally cast the value to this type
        """
        a = xml.get(name)
        if a is None:
            raise InvalidXmlError('Attribute %s not found in <%s>' % (
                    a, xml.tag))
        if type:
            a = type(a)
        return a

    def parseParameter(self, xml):
        if len(xml) != 0:
            raise InvalidXmlError('Unexpected children in <%s>' % xml.tag)

        name = self.attribNotNone(xml, 'name')
        value = self.attribNotNone(xml, 'value')
        return (name, value)

    def parseAlgorithm(self, xml):
        id = self.attribNotNone(xml, 'scriptId', long)
        params = {}
        for x in xml:
            if x.tag != self.preNs('Parameter'):
                raise InvalidXmlError(
                    'Expected <Parameter>, found <%s>' % x.tag)
            name, value = self.parseParameter(x)
            if name in params:
                raise InvalidXmlError(
                    'Duplicate parameter name: %s' % name)
            params[name] = value

        return Algorithm(id, params)

    def parseTable(self, xml):
        originalFileId = self.attribNotNone(xml, 'originalFileId', long)
        if len(xml) != 0:
            raise InvalidXmlError('Unexpected children in <%s>' % xml.tag)

        return originalFileId

    def parseImage(self, xml):
        id = self.attribNotNone(xml, 'id', long)
        z = long(xml.get('z'))
        c = xml.get('c')
        if c is not None:
            c = map(long, c.split(','))
        t = long(xml.get('t'))

        if len(xml) != 0:
            raise InvalidXmlError('Unexpected children in <%s>' % xml.tag)

        return Image(id, z, c, t)

    def parseAnnotation(self, xml):
        annotationId = self.attribNotNone(xml, 'annotationId', long)
        if len(xml) != 0:
            raise InvalidXmlError('Unexpected children in <%s>' % xml.tag)

        return annotationId

    def parseClassLabel(self, xml):
        index = self.attribNotNone(xml, 'index', long)
        label = self.parseLabel(xml)
        return (index, label)

    def parseLabel(self, xml):
        if not xml.text:
            raise InvalidXmlError(
                'Expected text content in <%s>' % xml.tag)
        if len(xml) != 0:
            raise InvalidXmlError('Unexpected children in <%s>' % xml.tag)

        return xml.text

    def parsePrediction(self, xml):
        label = None

        id = self.attribNotNone(xml, 'imageId', long)
        z = long(xml.get('z'))
        c = xml.get('c')
        if c is not None:
            c = map(long, c.split(','))
        t = long(xml.get('t'))

        for x in xml:
            if x.tag == self.preNs('Label'):
                if label:
                    raise InvalidXmlError(
                        'Multiple <Label> found in <%s>' % xml.tag)
                label = self.parseLabel(x)

            else:
                # @todo Ignore additional elements instead of throwing?
                raise InvalidXmlError(
                    'Unexpected element <%s> found in <%s>' % (x.tag, xml.tag))

        return Prediction(id, z, c, t, label)


    def parseFeatureSet(self, xml):
        algorithm = None
        tableId = None
        images = []

        for x in xml:
            if x.tag == self.preNs('Algorithm'):
                if algorithm:
                    raise InvalidXmlError(
                        'Multiple <Algorithm> found in <%s>' % xml.tag)
                algorithm = self.parseAlgorithm(x)

            elif x.tag == self.preNs('FeatureTable'):
                if tableId is not None:
                    raise InvalidXmlError(
                        'Multiple <FeatureTable> found in <%s>' %
                        xml.tag)
                tableId = self.parseTable(x)

            elif x.tag == self.preNs('Image'):
                images.append(self.parseImage(x))

            else:
                raise InvalidXmlError(
                    'Unexpected element <%s> found in <%s>' % (x.tag, xml.tag))

        return FeatureSet(algorithm, tableId, images)

    def parseClassifierInstance(self, xml):
        algorithm = None
        features = []
        featuresTable = None
        weightsTable = None
        labels = {}

        for x in xml:
            if x.tag == self.preNs('Algorithm'):
                if algorithm:
                    raise InvalidXmlError(
                        'Multiple <Algorithm> found in <%s>' % xml.tag)
                algorithm = self.parseAlgorithm(x)

            elif x.tag == self.preNs('TrainingFeatures'):
                features.append(self.parseAnnotation(x))

            elif x.tag == self.preNs('SelectedFeaturesTable'):
                if featuresTable is not None:
                    raise InvalidXmlError(
                        'Multiple <SelectedFeaturesTable> found in <%s>' %
                        xml.tag)
                featuresTable = self.parseTable(x)

            elif x.tag == self.preNs('FeatureWeightsTable'):
                if weightsTable is not None:
                    raise InvalidXmlError(
                        'Multiple <FeatureWeightsTable> found in <%s>' %
                        xml.tag)
                weightsTable = self.parseTable(x)

            elif x.tag == self.preNs('ClassLabel'):
                index, name = self.parseClassLabel(x)
                if index in labels:
                    raise InvalidXmlError('Duplicate index: %s' % index)
                labels[index] = name

            else:
                raise InvalidXmlError(
                    'Unexpected element <%s> found in <%s>' % (x.tag, xml.tag))

        return ClassifierInstance(
            algorithm, features, featuresTable, weightsTable, labels)


    def parseClassifierPrediction(self, xml):
        algorithm = None
        predictions = []

        for x in xml:
            if x.tag == self.preNs('Algorithm'):
                if algorithm:
                    raise InvalidXmlError(
                        'Multiple <Algorithm> found in <%s>' % xml.tag)
                algorithm = self.parseAlgorithm(x)

            elif x.tag == self.preNs('Prediction'):
                predictions.append(self.parsePrediction(x))

            else:
                raise InvalidXmlError(
                    'Unexpected element <%s> found in <%s>' % (x.tag, xml.tag))

        return ClassifierPrediction(algorithm, predictions)



class Writer(object):

    def __init__(self):
        self.ns = 'http://www.openmicroscopy.org/Schemas/OME/2012-06'
        xml.etree.ElementTree.register_namespace(
            'SA', STRUCTUREDANNOTATIONS_NAMESPACE)

    def getNs(self, tag):
        a = tag.find('{')
        b = tag.find('}')
        if a == -1:
            assert(b == -1)
            return None

        assert(a == 0 and b > 0)
        return tag[(a + 1):b]

    def preNs(self, tag):
        return '{%s}%s' % (self.ns, tag)

    def preSA(self, tag):
        return '{%s}%s' % (STRUCTUREDANNOTATIONS_NAMESPACE, tag)

    def prefixWithDefaultNs(self, xml):
        """
        The XML library seems to require prefixes on everything:
        http://programmaticallyspeaking.com/serializing-non-qualified-attributes-with-elementtree.html

        This is a questionable hack which attempts to add a default namespace to
        attributes and elements which don't have a namespace, so that when the
        XML is written out with a default namespace specified it just works.

        Probably best to avoid calling this unless you have to.
        """
        for elem in xml.iter():
            # inherit the uri from the element
            uri = self.getNs(elem.tag)
            if not uri:
                elem.tag = self.preNs(elem.tag)
                uri = self.ns
            for k, v in elem.attrib.items():
                if k[0] != "{":
                    # replace the old attribute with a namespace-prefixed one
                    del elem.attrib[k]
                    k = "{%s}%s" % (uri, k)
                    elem.attrib[k] = v

    def writeOmeXml(self, file, root):
        tree = ElementTree(root)
        self.prefixWithDefaultNs(tree)
        tree.write(file, 'UTF-8', True, self.ns)

    def omeXml(self, featureSet=None, classifierInstance=None,
               classifierPrediction=None, id=None):
        root = Element('OME')
        ssa = SubElement(root, self.preSA('StructuredAnnotations'))

        attribs = { 'Namespace': CLASSIFIER_NAMESPACE }
        if id is not None:
            attribs['ID'] = str(id)
        sxa = SubElement(ssa, self.preSA('XMLAnnotation'), attribs)

        sv = SubElement(sxa, self.preSA('Value'))
        c = SubElement(sv, 'Classifier', { 'namespace': ADDITIONS_NAMESPACE } )

        if featureSet:
            c.append(self.xmlFeatureSet(featureSet))
        if classifierInstance:
            c.append(self.xmlClassifierInstance(classifierInstance))
        if classifierPrediction:
            c.append(self.xmlClassifierPrediction(classifierPrediction))

        return root

    def toString(self, xml):
        return tostring(xml)

    def xmlFeatureSet(self, featset):
        fs = Element('FeatureSet')
        a = self.xmlAlgorithm(featset.algorithm)
        fs.append(a)
        SubElement(fs, 'FeatureTable',
                   { 'originalFileId': str(featset.tableId) })

        for im in featset.images:
            xim = self.xmlImage(im)
            fs.append(xim)

        return fs

    def xmlClassifierInstance(self, classinst):
        ci = Element('ClassifierInstance')
        a = self.xmlAlgorithm(classinst.algorithm)
        ci.append(a)

        for tid in classinst.trainingIds:
            SubElement(ci, 'TrainingFeatures', { 'annotationId': str(tid) })

        SubElement(ci, 'SelectedFeaturesTable',
                   { 'originalFileId': str(classinst.selectedId) })

        SubElement(ci, 'FeatureWeightsTable',
                   { 'originalFileId': str(classinst.weightsId) })

        for (index, label) in classinst.labels.iteritems():
            cl = SubElement(ci, 'ClassLabel', { 'index': str(index) })
            cl.text = str(label)

        return ci

    def xmlClassifierPrediction(self, classpred):
        cp = Element('ClassifierPrediction')
        a = self.xmlAlgorithm(classpred.algorithm)
        cp.append(a)

        for pred in classpred.predictions:
            p = self.xmlPrediction(pred)
            cp.append(p)

        return cp


    def xmlAlgorithm(self, algorithm):
        a = Element('Algorithm', { 'scriptId': str(algorithm.id) })
        for (name, value) in algorithm.parameters.iteritems():
            p = SubElement(a, 'Parameter',
                           { 'name': str(name), 'value': str(value) })
        return a

    def xmlImage(self, image):
        im = Element('Image',
                     { 'id': str(image.id), 'z': str(image.z),
                       'c': ','.join(['%d' % n for n in image.c]),
                       't': str(image.t) })
        return im

    def xmlPrediction(self, prediction):
        p = Element('Prediction',
                    { 'imageId': str(prediction.id), 'z': str(prediction.z),
                      'c': ','.join(['%d'%n for n in prediction.c]),
                      't': str(prediction.t) })
        l = SubElement(p, 'Label')
        l.text = str(prediction.label)
        return p


