import time
import numpy
import ideep4py
from ideep4py import distribute

if not distribute.available():
    print ("Distribute feature not built into iDeep,",
           "please use 'cmake -Dmultinode=ON ..' to build ideep")
    exit()

size = 999999
total_size = 0
nlayer = 10
shape = [None]*nlayer

for layer in range(nlayer):
    shape[layer] = [size/(layer+1)]
    total_size += shape[layer][0]

src_bufs = [None]*nlayer
src_backups = [None]*nlayer
bufs_expect = [None]*nlayer
for layer in range(nlayer):
    src_bufs[layer] = numpy.zeros(shape[layer], numpy.float32)
    src_backups[layer] = numpy.zeros(shape[layer], numpy.float32)
    bufs_expect[layer] = numpy.zeros(shape[layer], numpy.float32)

print ("Initialize distributed computation")
distribute.init()

world_size = distribute.get_world_size()
print ("world size = %d" % (world_size))

rank = distribute.get_rank()
print ("rank = %d" % (rank))

for layer in range(nlayer):
    for i in range(shape[layer][0]):
        src_bufs[layer][i] = float(i)/(shape[layer][0]+1) + rank + layer*10

for layer in range(nlayer):
    src_bufs[layer] = ideep4py.mdarray(src_bufs[layer])
    src_backups[layer] = ideep4py.mdarray(src_backups[layer])
    ideep4py.basic_copyto(src_backups[layer], src_bufs[layer])

iter_num = 100
start = time.time()

# inplace
for i in range(iter_num):
    for layer in range(nlayer):
        ideep4py.basic_copyto(src_bufs[layer], src_backups[layer])
    for layer in range(nlayer):
        distribute.iallreduce(layer, src_bufs[layer])
    for layer in range(nlayer):
        distribute.wait(nlayer-1-layer)
    distribute.barrier()

end = time.time()

avg_time = (end-start)/iter_num
eff_bw = 2.0*(world_size-1)/world_size * total_size * 32 / avg_time/1000000000
print ("[%d] Allreduce done in %f seconds, bw=%fGbps"
       % (rank, avg_time, eff_bw))
distribute.finalize()

if rank == 0:
    print ("Generate expected result...")
for layer in range(nlayer):
    for r in range(world_size):
        for i in range(shape[layer][0]):
            bufs_expect[layer][i] += (i+0.0)/(shape[layer][0]+1) + r + layer*10


for layer in range(nlayer):
    if rank == 0:
        print ("[%d] Validate inplace result for layer %d:" % (rank, layer))
    numpy.testing.assert_allclose(src_bufs[layer],
                                  bufs_expect[layer],
                                  rtol=1e-06)
    if rank == 0:
        print ("pass!")
