# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
# libspectral_accel.so: the spectral accelerator nvc loads with --load (and Python with ctypes).
CUDA ?= /usr/local/cuda

libspectral_accel.so: spectral_accel.o
	g++ -shared -fopenmp -o $@ spectral_accel.o -L$(CUDA)/lib64 -Wl,-rpath,$(CUDA)/lib64 -lcudart -lm

spectral_accel.o: spectral_accel.cu spectral_stages.inc spectral_accel.h
	$(CUDA)/bin/nvcc -O3 -Xcompiler -fPIC -Xcompiler -fopenmp -Xcompiler -march=native -c -o $@ spectral_accel.cu

clean:
	rm -f libspectral_accel.so *.o
