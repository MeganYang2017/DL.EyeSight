# Copyright (c) 2009 IW.
# All rights reserved.
#
# Author: liuguiyang <liuguiyangnwpu@gmail.com>
# Date:   2018/3/4

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import sys
import time
from datetime import datetime

import numpy as np
import tensorflow as tf

from eagle.brain.solver.solver import Solver


class YoloUSolver(Solver):
    def __init__(self, dataset, net, common_params, solver_params):
        super(YoloUSolver, self).__init__(dataset, net, common_params, solver_params)

        # process params
        self.width = int(common_params['image_size'])
        self.height = int(common_params['image_size'])
        self.batch_size = int(common_params['batch_size'])
        self.max_objects = int(common_params['max_objects_per_image'])

        self.moment = float(solver_params['moment'])
        self.learning_rate = float(solver_params['lr'])
        self.train_dir = str(solver_params['train_dir'])
        self.max_iterators = int(solver_params['max_iterators'])
        self.pretrain_path = str(solver_params['pretrain_model_path'])

        self.dataset = dataset
        self.net = net

        # construct graph
        self.construct_graph()

    def _train(self):
        """Train model

        Create an optimizer and apply to all trainable variables.

        Args:
          total_loss: Total loss from net.loss()
          global_step: Integer Variable counting the number of training steps
          processed
        Returns:
          train_op: op for training
        """

        opt = tf.train.MomentumOptimizer(self.learning_rate, self.moment)
        grads = opt.compute_gradients(self.total_loss)

        apply_gradient_op = opt.apply_gradients(grads,
                                                global_step=self.global_step)

        return apply_gradient_op

    def construct_graph(self):
        # construct graph
        self.global_step = tf.Variable(0, trainable=False)
        self.images = tf.placeholder(tf.float32, (
        self.batch_size, self.height, self.width, 3))
        self.labels = tf.placeholder(tf.float32,
                                     (self.batch_size, self.max_objects, 5))
        self.objects_num = tf.placeholder(tf.int32, (self.batch_size))

        self.predicts = self.net.inference(self.images)

        self.net.set_cell_size(grid_size=9)
        total_loss_g9, nilboy_g9 = self.net.loss(
            self.predicts["predicts_g9"], self.labels, self.objects_num)
        self.net.set_cell_size(grid_size=15)
        total_loss_g15, nilboy_g15 = self.net.loss(
            self.predicts["predicts_g15"], self.labels, self.objects_num)

        # self.nilboy_g9 = nilboy_g9
        # self.nilboy_g15 = nilboy_g15
        self.total_loss = 0.5 * (total_loss_g9 + total_loss_g15)
        tf.summary.scalar('loss', self.total_loss)
        self.train_op = self._train()

    def solve(self):
        saver_pretrain = tf.train.Saver(max_to_keep=3)
        saver_train = tf.train.Saver(max_to_keep=3)

        init = tf.global_variables_initializer()

        summary_op = tf.summary.merge_all()

        sess = tf.Session()

        sess.run(init)
        if self.pretrain_path != "None":
            saver_pretrain.restore(sess, self.pretrain_path)

        summary_writer = tf.summary.FileWriter(self.train_dir, sess.graph)

        for step in range(self.max_iterators):
            start_time = time.time()
            np_images, np_labels, np_objects_num = self.dataset.batch()

            _, loss_value = sess.run(
                [self.train_op, self.total_loss],
                feed_dict={
                    self.images: np_images,
                    self.labels: np_labels,
                    self.objects_num: np_objects_num
                })

            duration = time.time() - start_time

            assert not np.isnan(loss_value), 'Model diverged with loss = NaN'

            if step % 1 == 0:
                num_examples_per_step = self.dataset.batch_size
                examples_per_sec = num_examples_per_step / duration
                sec_per_batch = float(duration)

                format_str = ('%s: step %d, loss = %.2f '
                              '(%.1f examples/sec; %.3f sec/batch)')
                print(format_str % (datetime.now(), step, loss_value,
                                    examples_per_sec, sec_per_batch))
                sys.stdout.flush()
            if step % 1000 == 0:
                summary_str = sess.run(
                    summary_op,
                    feed_dict={
                        self.images: np_images,
                        self.labels: np_labels,
                        self.objects_num: np_objects_num
                    })
                summary_writer.add_summary(summary_str, step)
            if step % 5000 == 0:
                saver_train.save(sess,
                                 self.train_dir + '/model.ckpt')
        sess.close()

    def process_predicts(self, predicts, cell_size):
        p_classes = predicts[0, :, :, 0:1]
        C = predicts[0, :, :, 1:3]
        coordinate = predicts[0, :, :, 3:]

        p_classes = np.reshape(p_classes, (cell_size, cell_size, 1, 1))
        C = np.reshape(C, (cell_size, cell_size, 2, 1))

        P = C * p_classes

        # print P[5,1, 0, :]

        index = np.argmax(P)
        index = np.unravel_index(index, P.shape)
        class_num = index[3]

        coordinate = np.reshape(coordinate, (cell_size, cell_size, 2, 4))
        max_coordinate = coordinate[index[0], index[1], index[2], :]

        xcenter = max_coordinate[0]
        ycenter = max_coordinate[1]
        w = max_coordinate[2]
        h = max_coordinate[3]

        xcenter = (index[1] + xcenter) * (self.width / cell_size)
        ycenter = (index[0] + ycenter) * (self.height / cell_size)

        w = w * self.width
        h = h * self.height

        xmin = xcenter - w / 2.0
        ymin = ycenter - h / 2.0

        xmax = xmin + w
        ymax = ymin + h

        xmin = max(0, xmin)
        xmax = max(0, xmax)
        return xmin, ymin, xmax, ymax, class_num

    def model_predict(self, single_image):
        saver_pretrain = tf.train.Saver(max_to_keep=3)

        init = tf.global_variables_initializer()
        sess = tf.Session()
        sess.run(init)

        if self.pretrain_path != "None":
            saver_pretrain.restore(sess, self.pretrain_path)

        start_time = time.time()

        predics_info = sess.run(
            self.predicts,
            feed_dict={
                self.images: single_image
            })

        duration = time.time() - start_time

        xmin, ymin, xmax, ymax, class_num = self.process_predicts(
            predics_info["predicts_g9"], cell_size=9)
        # xmin, ymin, xmax, ymax, class_num = self.process_predicts(
        #     predics_info["predicts_g15"])
        sess.close()

        return (xmin, ymin, xmax, ymax, class_num)
