# Copyright (c) 2009 IW.
# All rights reserved.
#
# Author: liuguiyang <liuguiyangnwpu@gmail.com>
# Date:   2018/3/5

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from configparser import ConfigParser


def process_config(conf_file):
    """process configure file to generate CommonParams, DataSetParams, NetParams

    Args:
        conf_file: configure file path
    Returns:
        CommonParams, DataSetParams, NetParams, SolverParams
    """
    common_params = {}
    dataset_params = {}
    net_params = {}
    solver_params = {}
    box_encoder_params = {}

    # configure_parser
    config = ConfigParser()
    config.read(conf_file, encoding="utf8")

    # sections and options
    for section in config.sections():
        # construct common_params
        if section == 'Common':
            for option in config.options(section):
                common_params[option] = config.get(section, option)
        # construct dataset_params
        if section == 'DataSet':
            for option in config.options(section):
                dataset_params[option] = config.get(section, option)
        # construct net_params
        if section == 'Net':
            for option in config.options(section):
                net_params[option] = config.get(section, option)
        # construct solver_params
        if section == 'Solver':
            for option in config.options(section):
                solver_params[option] = config.get(section, option)

        # construct box_encoder_params
        if section == 'BoxEncoder':
            for option in config.options(section):
                box_encoder_params[option] = config.get(section, option)

    # 检测当前任务是需要进行测试还是进行训练
    if "is_predict" in common_params.keys():
        if common_params["is_predict"] == "True":
            common_params["is_predict"] = True
            common_params["batch_size"] = 1
        else:
            common_params["is_predict"] = False

    if len(box_encoder_params) == 0:
        return common_params, dataset_params, net_params, solver_params

    return common_params, dataset_params, net_params, solver_params, box_encoder_params


if __name__ == '__main__':
    common_params, dataset_params, net_params, solver_params = process_config(
        "../../conf/yolo_unet_train.cfg")
    print(common_params)
    print(dataset_params)
    # import json
    # print(json.loads(dataset_params["classes"]))
    # print(net_params["aspect_ratios"])
    # print(json.loads(net_params["aspect_ratios"]))