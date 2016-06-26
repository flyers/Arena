import numpy as np
import mxnet as mx
from arena.operators import *
from mxnet.lr_scheduler import FactorScheduler
from arena.utils import *
from arena import Base
import argparse
import gym
import gym.spaces

def normal_sym(action_num):
    # define the network structure of Gaussian policy
    data = mx.symbol.Variable('data')
    policy_mean = mx.symbol.FullyConnected(data=data, name='fc_mean_1', num_hidden=128)
    policy_mean = mx.symbol.Activation(data=policy_mean, name='fc_mean_tanh_1', act_type='tanh')
    policy_mean = mx.symbol.FullyConnected(data=policy_mean, name='fc_mean_2', num_hidden=128)
    policy_mean = mx.symbol.Activation(data=policy_mean, name='fc_mean_tanh_2', act_type='tanh')
    policy_mean = mx.symbol.FullyConnected(data=policy_mean, name='fc_output', num_hidden=action_num)

    policy_var = mx.symbol.Variable('var')
    # policy_var = mx.symbol.FullyConnected(data=data, name='fc_var', num_hidden=action_num)
    # policy_var = mx.symbol.exp(data=policy_var, name='var_out')

    net = mx.symbol.Custom(mean=policy_mean, var=policy_var,
                           name='policy', op_type='LogNormalPolicy', implicit_backward=False)
    return net


def critic_sym():
    data = mx.symbol.Variable('data')
    # define the network structure of critics network
    critic_net = mx.symbol.FullyConnected(data=data, name='fc_critic_1', num_hidden=128)
    critic_net = mx.symbol.Activation(data=critic_net, name='fc_critic_relu_1', act_type='relu')
    critic_net = mx.symbol.FullyConnected(data=critic_net, name='fc_critic_2', num_hidden=128)
    critic_net = mx.symbol.Activation(data=critic_net, name='fc_critic_relu_2', act_type='relu')
    critic_net = mx.symbol.FullyConnected(data=critic_net, name='fc_critic_3', num_hidden=1)
    target = mx.symbol.Variable('critic_label')
    critic_net = mx.symbol.LinearRegressionOutput(data=critic_net, name='critic', label=target, grad_scale=1)

    return critic_net

# convert normalized action [-1,1] back to original action space
def scale_action(action, action_space):
    lb = action_space.low
    ub = action_space.high
    scaled_action = lb + (action + 1.) * 0.5 * (ub - lb)
    scaled_action = np.clip(scaled_action, lb, ub)
    return scaled_action


parser = argparse.ArgumentParser(description='Script to train controllers for continuous environments in gym by advantage actor-critic algorithm.')
parser.add_argument('--lr', type=float, default=.001, help='the initial learning rate')
parser.add_argument('--lr-factor', type=float, default=1.,
                    help='times the lr with a factor for every lr-factor-iter iter')
parser.add_argument('--lr-factor-iter', type=float, default=1.,
                    help='the number of iteration to factor the lr')
parser.add_argument('--num-iters', type=int, default=500,
                    help='the number of training iterations')
parser.add_argument('--batch-size', type=int, default=4000,
                    help='the batch size')
parser.add_argument('--ctx', type=str, default='gpu',
                    help='Running Context. E.g `--ctx gpu` or `--ctx gpu1` or `--ctx cpu`')
parser.add_argument('--optimizer', default='sgd', type=str, choices=['sgd', 'adam'],
                    help='choice of the optimizer, adam or sgd')
parser.add_argument('--clip-gradient', default=True, type=str,
                    help='whether to clip the gradient')
parser.add_argument('--save-model', default=False, type=str,
                    help='whether to save the final model')
args = parser.parse_args()

discount = 0.99
n_itr = args.num_iters
batch_size = args.batch_size
lr_scheduler = FactorScheduler(args.lr_factor_iter, args.lr_factor)
ctx = parse_ctx(args.ctx)
ctx = mx.Context(*ctx[0])

# continuous action space environment
env = gym.make('Pendulum-v0')
T = env.spec.timestep_limit

observation_shape = env.observation_space.shape
action_shape = env.action_space.shape
policy_data_shapes = {'data': (batch_size,) + observation_shape,
                      'var': (batch_size, ) + action_shape,
                      'policy_score': (batch_size,),
                      'policy_backward_action': (batch_size,) + action_shape,
                      }
policy_sym = normal_sym(action_shape[0])
policy_net = Base(data_shapes=policy_data_shapes, sym_gen=policy_sym, name='a2c-a',
                  initializer=mx.initializer.Xavier(rnd_type='gaussian', factor_type='avg', magnitude=1.0), ctx=ctx)

critic_data_shapes = {'data': (batch_size,) + observation_shape,
                      'critic_label': (batch_size,),
                      }
critic_sym = critic_sym()
critic_net = Base(data_shapes=critic_data_shapes, sym_gen=critic_sym, name='a2c-c',
                  initializer=mx.initializer.Xavier(rnd_type='gaussian', factor_type='avg', magnitude=1.0), ctx=ctx)

if args.optimizer == 'sgd':
    optimizer = mx.optimizer.create(name='sgd', learning_rate=args.lr,
                                    lr_scheduler=lr_scheduler, momentum=0.9,
                                    clip_gradient=None, rescale_grad=1.0, wd=0.)
elif args.optimizer == 'adam':
    optimizer = mx.optimizer.create(name='adam', learning_rate=args.lr,
                                    lr_scheduler=lr_scheduler)
updater1 = mx.optimizer.get_updater(optimizer)
updater2 = mx.optimizer.get_updater(optimizer)

for itr in xrange(n_itr):
    paths = []
    counter = batch_size
    N = 0
    while counter > 0:
        N += 1
        observations = []
        actions = []
        rewards = []

        observation = env.reset()
        for step in xrange(T):
            action = policy_net.forward(is_train=False,
                                        data=observation.reshape(1, observation.size),
                                        var=1.*np.ones((1,)+action_shape),
                                        )[0].asnumpy()
            action = action[0]
            next_observation, reward, terminal, _ = env.step(scale_action(action, env.action_space))
            observations.append(observation)
            actions.append(action)
            rewards.append(reward)
            observation = next_observation
            if terminal:
                break

        counter -= (step + 1)
        observations = np.array(observations)
        rewards = np.array(rewards)
        critic_outputs = critic_net.forward(is_train=False,
                                            data=observations,)
        critics = critic_outputs[0].asnumpy().reshape(rewards.shape)
        q_estimations = discount_cumsum(rewards, discount)
        advantages = q_estimations - critics
        path = dict(
            actions=np.array(actions),
            rewards=rewards,
            observations=observations,
            q_estimations=q_estimations,
            advantages=advantages,
        )
        paths.append(path)

    observations = np.concatenate([p["observations"] for p in paths])
    actions = np.concatenate([p["actions"] for p in paths])
    q_estimations = np.concatenate([p["q_estimations"] for p in paths])
    advantages = np.concatenate([p['advantages'] for p in paths])
    cur_batch_size = observations.shape[0]
    policy_outputs = policy_net.forward(is_train=True,
                                        data=observations,
                                        var=1.*np.ones((cur_batch_size,)+action_shape),
                                        )
    critic_outputs = critic_net.forward(is_train=True,
                                        data=observations)
    policy_actions = policy_outputs[0].asnumpy()
    means = policy_outputs[1].asnumpy()
    vars = policy_outputs[2].asnumpy()
    critics = critic_outputs[0].asnumpy()
    policy_net.backward(policy_score=advantages,
                        policy_backward_action=actions.reshape(actions.shape))
    critic_net.backward(critic_label=q_estimations.reshape(q_estimations.size,))
    for grad in policy_net.params_grad.values():
        grad[:] = grad[:] / cur_batch_size
    for grad in critic_net.params_grad.values():
        grad[:] = grad[:] / cur_batch_size
    if args.clip_gradient:
        norm_clipping(policy_net.params_grad, 10)
        norm_clipping(critic_net.params_grad, 10)
    policy_net.update(updater1)
    critic_net.update(updater2)
    print 'Epoch:%d, Average Return:%f, Max Return:%f, Min Return:%f, Num Traj:%d, Average Baseline:%f, AveragePolicyMean:%f, AveragePolicyVar:%f' \
          %(itr, np.mean([sum(p["rewards"]) for p in paths]),
            np.max([sum(p["rewards"]) for p in paths]),
            np.min([sum(p["rewards"]) for p in paths]),
            N, critics.mean(),
            means.mean(),vars.mean()
            )

if args.save_model:
    policy_net.save_params(dir_path='./', epoch=itr)
