# --------------------------------------------------------
# Tensorflow Faster R-CNN
# Licensed under The MIT License [see LICENSE for details]
# Written by Xinlei Chen
# --------------------------------------------------------

# --------------------------------------------------------
# [Modified by Yunqiu Xu]
# Ref:
#   https://leonardoaraujosantos.gitbooks.io/artificial-inteligence/content/object_localization_and_detection.html
#   http://blog.csdn.net/shenxiaolu1984/article/details/51152614
#   http://closure11.com/rcnn-fast-rcnn-faster-rcnn%E7%9A%84%E4%B8%80%E4%BA%9B%E4%BA%8B/
#   http://blog.csdn.net/lanran2/article/details/60143861

# Why Faster RCNN is faster : RPN
#   RCNN: 
#      get proposal --> get features(CNN) --> SVM --> bbox regression
#   Fast RCNN: 
#      send proposal and features to ROI pooling --> combine bbox and SVM together
#   Faster RCNN:
#      get features first --> get proposals from RPN --> send proposal and features to ROI pooling
# ---------------------------------------------------------

# ------------- To do 1: Multiple Scale Faster-RCNN ------
# Combine both global and local features --> enhance hand detecting in an image
# Collect features not only conv5, but also conv3 and conv4, then incorporate them
# Implementation: 
#   1. For conv3, conv4, conv5, each conv is only followed with ReLU, remove Max-pooling layer.
#   2. Take their output as the input of 3 corresponding ROI pooling layers and normalization layers
#   3. Concat and shrink normalization layers as input of fc layers
#   4. roi pooling in fc layers: make prediction of class and position
# --------------------------------------------------------
# ------------- To do 2: Weight Normalization ------------
# Features in shallower layers: larger-scaled values
# Features in deeper layers: smaller-scaled values
# To combine the features of 3 conv layers, we need to normalize them
# Implementation:
#   1. Put each feature into normalization layer(see the equations)
#   2. Each pixel xi is normalized, then multiply scaling factor ri
#   3. Use backpropagation to get ri in training step, we need to build loop here
#   4. After normalization, the features will be concated
# --------------------------------------------------------
# ------------- To do 3 Add New Layer --------------------
# 1. Each RPN needs a normalization layer
# 2. Add two more ROI pooling layers in detector part
# 3. Each ROI pooling layer needs a normalization layer
# 4. After each concatenation(2 positions in total), we need a 1*1 conv layer
# --------------------------------------------------------


from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import tensorflow.contrib.slim as slim
from tensorflow.contrib.slim import losses
from tensorflow.contrib.slim import arg_scope
import numpy as np

from nets.network import Network
from model.config import cfg

class vgg16(Network):
  def __init__(self, batch_size=1):
    Network.__init__(self, batch_size=batch_size)
    self._arch = 'vgg16'

  def build_network(self, sess, is_training=True):
    with tf.variable_scope('vgg_16', 'vgg_16'):
      # select initializers
      if cfg.TRAIN.TRUNCATED:
        initializer = tf.truncated_normal_initializer(mean=0.0, stddev=0.01)
        initializer_bbox = tf.truncated_normal_initializer(mean=0.0, stddev=0.001)
      else:
        initializer = tf.random_normal_initializer(mean=0.0, stddev=0.01)
        initializer_bbox = tf.random_normal_initializer(mean=0.0, stddev=0.001)

      # [VGG16] conv1
      # input shape : 224 * 224 * 3
      # conv 64 * 3 * 3
      # conv 64 * 3 * 3
      # maxpool 2 * 2
      net = slim.repeat(self._image, 2, slim.conv2d, 64, [3, 3],
                        trainable=False, scope='conv1')
      net = slim.max_pool2d(net, [2, 2], padding='SAME', scope='pool1')

      # [VGG16] conv2
      # conv 128 * 3 * 3
      # conv 128 * 3 * 3
      # maxpool 2 * 2
      net = slim.repeat(net, 2, slim.conv2d, 128, [3, 3],
                        trainable=False, scope='conv2')
      net = slim.max_pool2d(net, [2, 2], padding='SAME', scope='pool2')


      # [VGG16] conv3
      # conv 256 * 3 * 3
      # conv 256 * 3 * 3
      # conv 256 * 3 * 3
      # maxpool 2 * 2
      net = slim.repeat(net, 3, slim.conv2d, 256, [3, 3],
                        trainable=is_training, scope='conv3')
      to_be_normalized_1 = net
      # [Hand Detection] REMOVE net = slim.max_pool2d(net, [2, 2], padding='SAME', scope='pool3') 

      # [VGG16] conv4
      # conv 512 * 3 * 3
      # conv 512 * 3 * 3
      # conv 512 * 3 * 3
      # maxpool 2 * 2
      net = slim.repeat(net, 3, slim.conv2d, 512, [3, 3],
                        trainable=is_training, scope='conv4')
      to_be_normalized_2 = net
      # [Hand Detection] REMOVE net = slim.max_pool2d(net, [2, 2], padding='SAME', scope='pool4') 

      # [VGG16] conv5
      # conv 512 * 3 * 3
      # conv 512 * 3 * 3
      # conv 512 * 3 * 3
      # maxpool 2 * 2
      net = slim.repeat(net, 3, slim.conv2d, 512, [3, 3],
                        trainable=is_training, scope='conv5')
      to_be_normalized_3 = net
      
      # [Hand detection]
      # Use the result of conv3, conv4 and conv5
      # normalize and concat them, then use 1*1 conv, then use RPN
      # use the result of 3 layers and RPN in training loop

      # // self._act_summaries.append(net)
      # // self._layers['head'] = net
      # // self._anchor_component() # Yunqiu Xu: generate anchors?

# ------------- RPN Begin --------------------------------
## %%%%%%%%%% RPN Begin %%%%%%%%%% ##
      # [Faster RCNN] RPN: put features into RPN layer --> get proposals
      # input features(or anchors?), output rois(proposals)
      # [Hand Detection] Normalize , concat, then use 1*1 conv, finally the data will be treated as the input here
      rpn = slim.conv2d(net, 512, [3, 3], trainable=is_training, weights_initializer=initializer, scope="rpn_conv/3x3")
      self._act_summaries.append(rpn)
      rpn_cls_score = slim.conv2d(rpn, self._num_anchors * 2, [1, 1], trainable=is_training,
                                  weights_initializer=initializer,
                                  padding='VALID', activation_fn=None, scope='rpn_cls_score')
      # [Hand Detection] change it so that the score has 2 as its channel size
      rpn_cls_score_reshape = self._reshape_layer(rpn_cls_score, 2, 'rpn_cls_score_reshape')
      rpn_cls_prob_reshape = self._softmax_layer(rpn_cls_score_reshape, "rpn_cls_prob_reshape")
      rpn_cls_prob = self._reshape_layer(rpn_cls_prob_reshape, self._num_anchors * 2, "rpn_cls_prob")
      rpn_bbox_pred = slim.conv2d(rpn, self._num_anchors * 4, [1, 1], trainable=is_training,
                                  weights_initializer=initializer,
                                  padding='VALID', activation_fn=None, scope='rpn_bbox_pred')
      if is_training:
        rois, roi_scores = self._proposal_layer(rpn_cls_prob, rpn_bbox_pred, "rois")
        rpn_labels = self._anchor_target_layer(rpn_cls_score, "anchor")
        # Try to have a determinestic order for the computing graph, for reproducibility
        with tf.control_dependencies([rpn_labels]):
          rois, _ = self._proposal_target_layer(rois, roi_scores, "rpn_rois")
      else:
        if cfg.TEST.MODE == 'nms':
          rois, _ = self._proposal_layer(rpn_cls_prob, rpn_bbox_pred, "rois")
        elif cfg.TEST.MODE == 'top':
          rois, _ = self._proposal_top_layer(rpn_cls_prob, rpn_bbox_pred, "rois")
        else:
          raise NotImplementedError
# ------------- RPN End ----------------------------------

# ------------- ROI Pooling Begin ------------------------
      # [Faster RCNN] build roi pooling layer(here is same with RCNN)
      # [Hand Detection] add another 2 roi pooling layer
      # Input: proposals(rois) from RPN and features from CNN 
      if cfg.POOLING_MODE == 'crop':
        pool5 = self._crop_pool_layer(net, rois, "pool5")
      else:
        raise NotImplementedError
# ------------- ROI Pooling End --------------------------

      # [Hand Detection] Then we use 3 normalize layers
      # [Hand Detection] Then we concat them
      # [Hand Detection] Then we use 1*1 conv to return the channel size


      # [VGG16] flatten
      pool5_flat = slim.flatten(pool5, scope='flatten')
      # [VGG16] dense 4096 + dropout
      fc6 = slim.fully_connected(pool5_flat, 4096, scope='fc6')
      if is_training:
        fc6 = slim.dropout(fc6, keep_prob=0.5, is_training=True, scope='dropout6')
      # [VGG16] dense 4096 + dropout
      fc7 = slim.fully_connected(fc6, 4096, scope='fc7')
      if is_training:
        fc7 = slim.dropout(fc7, keep_prob=0.5, is_training=True, scope='dropout7')
      
      # [Faster RCNN] get cls_score(class) and bbox_predict(position)
      cls_score = slim.fully_connected(fc7, self._num_classes, 
                                       weights_initializer=initializer,
                                       trainable=is_training,
                                       activation_fn=None, scope='cls_score')
      cls_prob = self._softmax_layer(cls_score, "cls_prob")
      bbox_pred = slim.fully_connected(fc7, self._num_classes * 4, 
                                       weights_initializer=initializer_bbox,
                                       trainable=is_training,
                                       activation_fn=None, scope='bbox_pred')

      self._predictions["rpn_cls_score"] = rpn_cls_score
      self._predictions["rpn_cls_score_reshape"] = rpn_cls_score_reshape
      self._predictions["rpn_cls_prob"] = rpn_cls_prob
      self._predictions["rpn_bbox_pred"] = rpn_bbox_pred
      self._predictions["cls_score"] = cls_score
      self._predictions["cls_prob"] = cls_prob
      self._predictions["bbox_pred"] = bbox_pred
      self._predictions["rois"] = rois

      self._score_summaries.update(self._predictions)

      return rois, cls_prob, bbox_pred
