#include <stdlib.h>
#include <zephyr.h>
#include <init.h>
#include <errno.h>
#include <sys/math_extras.h>
#include <string.h>
#include <app_memory/app_memdomain.h>
#include <sys/mutex.h>
#include <sys/sys_heap.h>
#include <zephyr/types.h>

#include "platform/hal_heap.h"

#if CONFIG_HEAP_SIZE > 0
#define HEAP_BYTES CONFIG_HEAP_SIZE
#define POOL_SECTION .data

Z_GENERIC_SECTION(POOL_SECTION) static struct sys_heap z_malloc_heap;
Z_GENERIC_SECTION(POOL_SECTION) struct sys_mutex z_malloc_heap_mutex;
Z_GENERIC_SECTION(POOL_SECTION) static char z_malloc_heap_mem[HEAP_BYTES];


void *aligned_alloc(size_t alignment, size_t size) {
    int lock_ret;

    lock_ret = sys_mutex_lock(&z_malloc_heap_mutex, K_FOREVER);

    __ASSERT_NO_MSG(lock_ret == 0);

    void *ret = sys_heap_aligned_alloc(&z_malloc_heap, alignment, size);
    if (ret == NULL && size != 0) {
        errno = ENOMEM;
    }

    (void) sys_mutex_unlock(&z_malloc_heap_mutex);
    return ret;
}

void *malloc(size_t size)
{
    return aligned_alloc(__alignof__(z_max_align_t), size);
}

void *realloc(void *ptr, size_t requested_size)
{
    int lock_ret;

    lock_ret = sys_mutex_lock(&z_malloc_heap_mutex, K_FOREVER);
    __ASSERT_NO_MSG(lock_ret == 0);

    void *ret = sys_heap_aligned_realloc(&z_malloc_heap, ptr,
                                         __alignof__(z_max_align_t),
                                         requested_size);

    if (ret == NULL && requested_size != 0) {
        errno = ENOMEM;
    }

    (void) sys_mutex_unlock(&z_malloc_heap_mutex);

    return ret;
}

void free(void *ptr)
{
    int lock_ret;

    lock_ret = sys_mutex_lock(&z_malloc_heap_mutex, K_FOREVER);
    __ASSERT_NO_MSG(lock_ret == 0);
    sys_heap_free(&z_malloc_heap, ptr);
    (void) sys_mutex_unlock(&z_malloc_heap_mutex);
}

static int malloc_prepare(const struct device *unused)
{
    ARG_UNUSED(unused);

    sys_heap_init(&z_malloc_heap, z_malloc_heap_mem, HEAP_BYTES);

    sys_mutex_init(&z_malloc_heap_mutex);

    return 0;
}

SYS_INIT(malloc_prepare, APPLICATION, CONFIG_KERNEL_INIT_PRIORITY_DEFAULT);
#endif