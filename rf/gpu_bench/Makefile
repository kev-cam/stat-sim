CUDA ?= /usr/local/cuda
CXXFLAGS = -O3 -march=native -ffast-math -fopenmp

bench: bench.o cpu.o
	g++ -fopenmp -o $@ bench.o cpu.o -L$(CUDA)/lib64 -Wl,-rpath,$(CUDA)/lib64 -lcufft -lcudart -lfftw3 -lfftw3f -lm

bench.o: bench.cu cpu.h
	$(CUDA)/bin/nvcc -O3 -Xcompiler -fopenmp -c -o $@ bench.cu

cpu.o: cpu.cpp cpu.h
	g++ $(CXXFLAGS) -c -o $@ cpu.cpp

clean:
	rm -f bench *.o
