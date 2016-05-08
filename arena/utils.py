import mxnet as mx
import mxnet.ndarray as nd
import os
import numpy
import json
import re
import logging
from collections import namedtuple, OrderedDict

ExecutorPoolKey = namedtuple('ExecutorPoolKey', ['data_shapes_items', 'sym_name'])
ExecutorPoolKey.__new__.__defaults__ = (None, None)

_ctx = mx.cpu()
_numpy_rng = numpy.random.RandomState(123456)


def get_default_ctx():
    return _ctx


def get_numpy_rng():
    return _numpy_rng


def get_saving_path(prefix="", epoch=None,):
    sym_saving_path = os.path.join('%s-symbol.json' % prefix)
    if epoch is not None:
        param_saving_path = os.path.join('%s-%05d.params' % (prefix, epoch))
    else:
        param_saving_path = os.path.join('%s.params' % prefix)
    misc_saving_path = os.path.join('%s-misc.json' % prefix)
    return sym_saving_path, param_saving_path, misc_saving_path


def save_params(dir_path=os.curdir, epoch=None, name="", params=None, aux_states=None, ctx=mx.cpu()):
    prefix = os.path.join(dir_path, name)
    _, param_saving_path, _ = get_saving_path(prefix, epoch)
    #TODO Remove the (dir_path == "") condition in the future
    if not os.path.isdir(dir_path) and not (dir_path == ""):
        os.makedirs(dir_path)
    save_dict = {('arg:%s' % k): v.copyto(ctx) for k, v in params.items()}
    save_dict.update({('aux:%s' % k): v.copyto(ctx) for k, v in aux_states.items()})
    nd.save(param_saving_path, save_dict)
    return param_saving_path


def save_misc(dir_path=os.curdir, epoch=None, name="", content=None):
    prefix = os.path.join(dir_path, name)
    _, _, misc_saving_path = get_saving_path(prefix, epoch)
    with open(misc_saving_path, 'w') as fp:
        json.dump(content, fp)
    return misc_saving_path


def quick_save_json(dir_path=os.curdir, file_name="", content=None):
    file_path = os.path.join(dir_path, file_name)
    if not os.path.isdir(dir_path):
        os.makedirs(dir_path)
    with open(file_path, 'w') as fp:
        json.dump(content, fp)
    logging.info('Save json into %s' % file_path)


def block_all(sym_list):
    return [mx.symbol.BlockGrad(sym) for sym in sym_list]

def load_params(dir_path="", epoch=None, name=""):
    prefix = os.path.join(dir_path, name)
    _, param_loading_path, _ = get_saving_path(prefix, epoch)
    save_dict = nd.load(param_loading_path)
    arg_params = {}
    aux_params = {}
    for k, v in save_dict.items():
        tp, name = k.split(':', 1)
        if tp == 'arg':
            arg_params[name] = v
        if tp == 'aux':
            aux_params[name] = v
    return arg_params, aux_params, param_loading_path


def load_misc(dir_path="", epoch=None, name=""):
    prefix = os.path.join(dir_path, name)
    _, _, misc_saving_path = get_saving_path(prefix, epoch)
    with open(misc_saving_path, 'r') as fp:
        misc = json.load(fp)
    return misc


def update_on_kvstore(kv, params, params_grad):
    for ind, k in enumerate(params.keys()):
        kv.push(ind, params_grad[k], priority=-ind)
        kv.pull(ind, params[k], priority=-ind)


def parse_ctx(ctx_args):
    ctx = re.findall('([a-z]+)(\d*)', ctx_args)
    ctx = [(device, int(num)) if len(num) > 0 else (device, 0) for device, num in ctx]
    return ctx

'''
Function: get_npy_list
Description:
    Get a numpy-array list from a ndarray list
'''
def get_npy_list(ndarray_list):
    return [v.asnumpy() for v in ndarray_list]

class ExecutorDataShapePool(object):
    def __init__(self, ctx, sym, data_shapes, params, params_grad, aux_states):
        self.ctx = ctx
        self.sym = sym
        self.internal_syms = self.sym.get_internals()
        self.params = params
        self.params_grad = params_grad
        self.aux_states = aux_states
        self.inputs_grad_dict = {}
        self.basic_data_shapes = data_shapes.copy()
        self.exe_pool = {}
        self.base_exe = None
        self.base_exe = self.get()

    def get(self, batch_size=None, data_shapes=None, internal_sym_name=None):
        if batch_size is None and data_shapes is None:
            if self.base_exe is not None:
                return self.base_exe
            data_shapes_items = tuple(self.basic_data_shapes.items())
        elif data_shapes is not None:
            # The `data_shapes` field will not be used if `batch_size` is specified.
            new_data_shapes = self.basic_data_shapes.copy()
            for k, v in data_shapes.items():
                new_data_shapes[k] = v
            data_shapes_items = tuple(new_data_shapes.items())
        else:
            assert isinstance(batch_size, (int, long))
            data_shapes_items = tuple([(k, (batch_size,) + v[1:]) for k, v in
                               self.basic_data_shapes.items()])
        exe_key = ExecutorPoolKey(data_shapes_items=data_shapes_items, sym_name=internal_sym_name)
        if exe_key in self.exe_pool:
            return self.exe_pool[exe_key]
        else:
            if internal_sym_name is not None:
                # Compile a forward only executor for internal symbol
                internal_sym = self.internal_syms[internal_sym_name]
                data_inputs = {k: mx.nd.empty(v, ctx=self.ctx)
                               for k, v in data_shapes_items
                                if k in internal_sym.list_arguments()}
                params = {k: v for k, v in self.params.items() if k in internal_sym.list_arguments()}
                aux_states = {k: v for k, v in self.aux_states.items()
                              if k in internal_sym.list_auxiliary_states()}
                exe = internal_sym.bind(ctx=self.ctx, args=dict(params, **data_inputs),
                                            args_grad=None, grad_req='null', aux_states=aux_states)
                self.exe_pool[exe_key] = exe
            else:
                data_inputs = {k: mx.nd.empty(v, ctx=self.ctx)
                               for k, v in data_shapes_items}
                inputs_grad = {k: mx.nd.empty(v, ctx=self.ctx)
                               for k, v in data_shapes_items}
                self.inputs_grad_dict[data_shapes_items] = inputs_grad
                if len(self.exe_pool) == 0:
                    exe = self.sym.bind(ctx=self.ctx, args=dict(self.params, **data_inputs),
                                    args_grad=dict(self.params_grad.items() + inputs_grad.items()),
                                    aux_states=self.aux_states)
                else:
                    exe = self.sym.bind(ctx=self.ctx, args=dict(self.params, **data_inputs),
                                    args_grad=dict(self.params_grad.items() + inputs_grad.items()),
                                    aux_states=self.aux_states, shared_exec=self.base_exe)
                self.exe_pool[exe_key] = exe
            return exe
