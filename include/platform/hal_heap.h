#ifndef HAL_HEAP_H_INCLUDED
#define HAL_HEAP_H_INCLUDED

#include <stdlib.h>

__weak void *malloc(size_t size);
__weak void *realloc(void *ptr, size_t requested_size);
__weak void free(void *ptr);
__weak void *aligned_alloc(size_t alignment, size_t size);

#endif // HAL_HEAP_H_INCLUDED