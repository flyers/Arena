Arena
=======================================================================

[Arena](https://github.com/peterzcc/dist_train/tree/arena), A Distributed Asynchronous Reinforcement Learning package based on [MXNet](https://github.com/dmlc/mxnet)


### How to Install
Install the development version of [MXNet](https://github.com/dmlc/mxnet) first. After that, use `python setup.py develop --user` to install Arena.
Also, install the [Arcade Learning Environment (ALE)](https://github.com/mgbellemare/Arcade-Learning-Environment) if we want to run demo program that trains AI for Breakout. 

~~To install MXNet extensions, using `python mxnet-patch.py -p MXNET_PATH -t install`. Uninstall these extensions by `python mxnet-patch.py -p MXNET_PATH -t uninstall`. 
You need to recompile MXNet after installing the extensions. Also, the ``FFT/IFFT`` operators require CuFFT. Add `-lcufft` to the link flags in MXNet.~~

To compile & install MXNet on windows, the following cmake command may be helpful (run it under mxnet/build):

```
cmake -G "Visual Studio 12 2013 Win64" ^
-DCMAKE_BUILD_TYPE=Release ^
-DCMAKE_CONFIGURATION_TYPES="Release" ^
-DMKL_INCLUDE_DIR="C:\\Program Files (x86)\\IntelSWTools\\compilers_and_libraries_2016\\windows\\mkl\\include" ^
-DMKL_RT_LIBRARY="C:\\Program Files (x86)\\IntelSWTools\\compilers_and_libraries_2016\\windows\\mkl\\lib\\intel64\\mkl_rt.lib" ^
-DOpenCV_DIR="E:\ThirdParty\opencv-3.1\opencv\build\x64\vc12\lib" ^
-DZMQ_LIBRARY="D:\HKUST\libzmq\bin\x64\Release\v120\dynamic" ^
-DZMQ_INCLUDE_DIR="D:\HKUST\libzmq\include" ^
-DPROTOBUF_LIBRARY="D:\\HKUST\\protobuf\\cmake\\build\\release" ^
-DPROTOBUF_INCLUDE_DIR="D:\\HKUST\\protobuf\\src" ^
-DCUDNN_INCLUDE="C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v7.5\\include" ^
-DCUDNN_ROOT="C:\\Program Files\\NVIDIA GPU Computing Toolkit\\CUDA\\v7.5\\lib\\x64" ^
-DBLAS=MKL ..
```


### Design Principles
Keep parallelism in mind. Do not hide the key algorithms and keep the implementation readable and easy to hack.


### Examples
Run `python dqn_dist_demo.py` to train AI for Breakout.