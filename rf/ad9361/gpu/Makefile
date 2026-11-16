# Part of stat-sim. PolyForm Noncommercial License 1.0.0; commercial use needs a separate license (see LICENSE, COMMERCIAL.md).
CUDA ?= /usr/local/cuda

ad9361_gpu: ad9361_gpu.o
	g++ -fopenmp -o $@ ad9361_gpu.o -L$(CUDA)/lib64 -Wl,-rpath,$(CUDA)/lib64 -lcudart -lm

ad9361_gpu.o: ad9361_gpu.cu ad9361_kernels.h
	$(CUDA)/bin/nvcc -O3 -Xcompiler -fopenmp -Xcompiler -march=native -c -o $@ ad9361_gpu.cu

clean:
	rm -f ad9361_gpu *.o
