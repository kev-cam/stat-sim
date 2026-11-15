CUDA ?= /usr/local/cuda

pipe: pipe.o cpu_pipe.o
	g++ -fopenmp -o $@ pipe.o cpu_pipe.o -L$(CUDA)/lib64 -Wl,-rpath,$(CUDA)/lib64 -lcufft -lcudart -lfftw3f -lm

pipe.o: pipe.cu cpu_pipe.h tables.h
	$(CUDA)/bin/nvcc -O3 -Xcompiler -fopenmp -c -o $@ pipe.cu

cpu_pipe.o: cpu_pipe.cpp cpu_pipe.h tables.h
	g++ -O3 -march=native -ffast-math -fopenmp -c -o $@ cpu_pipe.cpp

tables.h: gen_tables.py
	python3 gen_tables.py

clean:
	rm -f pipe *.o
