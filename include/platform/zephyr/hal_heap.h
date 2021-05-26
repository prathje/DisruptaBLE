#ifndef HAL_ZEPHYR_HEAP_H_INCLUDED
#define HAL_ZEPHYR_HEAP_H_INCLUDED

__weak void *malloc(size_t size);
__weak void *realloc(void *ptr, size_t requested_size);
__weak void free(void *ptr);
__weak void *aligned_alloc(size_t alignment, size_t size);

#endif // HAL_HEAP_H_INCLUDED