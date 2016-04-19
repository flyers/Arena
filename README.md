Arena
=======================================================================

[Arena](https://github.com/peterzcc/dist_train/tree/arena), A Distributed Asynchronous Reinforcement Learning package based on [MXNet](https://github.com/dmlc/mxnet)

Use `python setup.py develop --user` to install the package.
Also, install the [Arcade Learning Environment (ALE)](https://github.com/mgbellemare/Arcade-Learning-Environment) and run `python dqn_dist_demo.py` to train AI for Breakout.

To install MXNet extensions, using `python mxnet-patch.py --path MXNET_PATH --type install`. Uninstall these extensions by `python mxnet-patch.py --path MXNET_PATH --type uninstall`. 
You need to recompile MXNet after installing the extensions. Also, the ``FFT/IFFT`` operators require CuFFT. Add `-lcufft` to the link flags in MXNet.