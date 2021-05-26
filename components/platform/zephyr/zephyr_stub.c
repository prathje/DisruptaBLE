#include <kernel.h>
#include <string.h>
#include <stdio.h>
#include <random/rand32.h>
#include <stdlib.h>

char *strdup(const char *s)
{
    char *dest = malloc(strlen(s)+1);

    if (dest) {
        strcpy(dest, s);
    }

    return dest;
}


char *strerror(int errnum) {
    static char tmp[16];
    sprintf(tmp, "%d", errnum);
    return tmp;
}

void pause() {
    k_thread_suspend(k_current_get());
}


void srand (unsigned int seed) {
}

int rand(void) {
    return sys_rand32_get();
}


unsigned long long int strtoull (const char* str, char** endptr, int base) {
    return strtoul(str, endptr, base);
}

// TODO: This disables support for IPN schemes!
int sscanf(const char *s, const char *format, ...)
{
    return 0;
}