# Author: Acer Zhang
# Datetime:2020/1/29 21:00
# Copyright belongs to the author.
# Please indicate the source for reprinting.

# Attention Scoring Neural Networks

import paddle.fluid as fluid
import paddle.fluid.initializer as parm_init
from paddle.fluid.param_attr import ParamAttr


def parm_msra():
    param = fluid.ParamAttr(
        initializer=parm_init.MSRA(),
        learning_rate=0.5,
        regularizer=fluid.regularizer.L2Decay(1.0),
        trainable=True)
    return param


def fc_with_name(ipt, fc_size: int, name: str, act: str = None):
    tmp = fluid.layers.fc(input=ipt,
                          size=fc_size,
                          param_attr=ParamAttr(name=name + '_fc_w_'),
                          bias_attr=ParamAttr(name=name + '_fc_b_'),
                          act=act)
    return tmp


def sample_gru_layer(ipt, fc_size: int, name: str):
    tmp = ipt
    for i in range(3):
        tmp = fluid.layers.dynamic_gru(input=tmp,
                                       size=fc_size // 3,
                                       is_reverse=(i % 2) != 0,
                                       param_attr=ParamAttr(name=name + '_gru_w_' + str(i)),
                                       bias_attr=ParamAttr(name=name + '_gru_b_' + str(i)))
        tmp = fluid.layers.fc(input=tmp,
                              size=fc_size,
                              param_attr=ParamAttr(name=name + '_after_gru_fc_w_' + str(i)),
                              bias_attr=ParamAttr(name=name + '_after_fc_b_' + str(i)))
    return tmp


def out_layers(ipt, name: str):
    tmp = fc_with_name(ipt, 128, name + "_out1_")
    tmp = fc_with_name(tmp, 32, name + "_out2_")
    tmp = fc_with_name(tmp, 1, name + "_out3_", act="tanh")
    return tmp


def keyword_extraction_with_attention_a(ipt_a, ipt_b):
    fc_a = fc_with_name(ipt_a, 300, "kea_a1")
    fc_b = fc_with_name(ipt_b, 300, "keb_a1")
    pool_a = fluid.layers.sequence_pool(input=fc_a, pool_type='max')
    pool_b = fluid.layers.sequence_pool(input=fc_b, pool_type='max')
    attention_weight = fc_with_name([pool_a, pool_b], 100, "softmax", "softmax")
    out = fluid.layers.elementwise_mul(pool_a, attention_weight)
    return out, attention_weight


def keyword_extraction_with_attention_b(ipt_c, attention_weight):
    fc_c = fc_with_name(ipt_c, 300, "kea_a1")
    pool_c = fluid.layers.sequence_pool(input=fc_c, pool_type='max')
    out = fluid.layers.elementwise_mul(pool_c, attention_weight)
    return out


class ASNN:
    a_out = None
    c_out = None

    def __init__(self, mode: int = 1, fc_size: int = 300):
        self.mode = mode
        self.fc_size = fc_size

    def main_network(self, key_f_vec, key_word_f_vec, virtual_input_f_vec):
        """

        :param key_f_vec: 原始答案分词VEC
        :param key_word_f_vec: 答案关键字分词VEC
        :param virtual_input_f_vec: 模拟输入分词VEC
        :return:
        """
        # 此处可删
        a_ipt = fc_with_name(key_f_vec, self.fc_size, "a_ipt")
        b_ipt = fc_with_name(key_word_f_vec, self.fc_size, "b_ipt")
        c_ipt = fc_with_name(virtual_input_f_vec, self.fc_size, "c_ipt")
        # 双向GRU网络
        a_gru1 = sample_gru_layer(a_ipt, self.fc_size, "a_gru1")
        b_gru1 = sample_gru_layer(b_ipt, self.fc_size, "b_gru1")
        c_gru1 = sample_gru_layer(c_ipt, self.fc_size, "c_gru1")
        # 注意力机制
        a_kea2, attention_weight = keyword_extraction_with_attention_a(a_gru1, b_gru1)
        c_kea2 = keyword_extraction_with_attention_b(c_gru1, attention_weight)
        # 输出层
        self.a_out = out_layers(a_kea2, "main_out")
        self.c_out = out_layers(c_kea2, "main_out")

    def req_cost(self, score):
        a_score = fluid.layers.ones_like(self.a_out)
        cost_a = fluid.layers.square_error_cost(self.a_out, a_score)
        cost_c = fluid.layers.square_error_cost(self.c_out, score)
        cost = cost_a + cost_c
        loss = fluid.layers.mean(cost) * 0.5
        return loss


# debug
data = fluid.data(name="test", shape=[-1, 1024], dtype="float32", lod_level=1)
s = fluid.data(name="test2", shape=[1], dtype="float32")
net = ASNN()
net.main_network(data, data, data)
net.req_cost(s)
