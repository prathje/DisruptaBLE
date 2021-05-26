/*
 * posix_zephyr_stub.h
 *
 * Description: contains the definitions of the hardware abstraction
 * layer interface for various hardware-specific functionality
 *
 */
#ifndef ZEPHYR_STUB_H_INCLUDED
#define ZEPHYR_STUB_H_INCLUDED

#include <math.h>

#ifndef ENONET
#define ENONET 80
#endif

#ifndef NI_MAXSERV
#define NI_MAXSERV 32
#endif


#ifndef RAND_MAX
#define RAND_MAX ((UINT32_MAX))
#endif

extern char *strerror(int errnum);

extern char  *strdup(const char *s);
extern void  pause();
extern void srand (unsigned int seed);
extern void srand (unsigned int seed);
extern int rand(void);

// TODO: This currently only supports long ints...
extern unsigned long long int strtoull (const char* str, char** endptr, int base);

#endif /* ZEPHYR_STUB_H_INCLUDED */
