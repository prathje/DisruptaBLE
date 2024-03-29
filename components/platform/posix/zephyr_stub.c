#ifdef PLATFORM_ZEPHYR

char *strerror(int errnum) {
    static char tmp[16];
    sprintf(tmp, "%d", errnum);
    return tmp;
}

char *strdup(const char *s)
{
	char *dest = malloc(strlen(s)+1);

	if (dest) {
		strcpy(dest, s);
	}

	return dest;
}


void pause() {
    k_thread_suspend(k_current_get());
}


void srand (unsigned int seed) {
    (void)seed; //NOOP for now
}

int rand(void) {
    return sys_rand32_get();
}


unsigned long long int strtoull (const char* str, char** endptr, int base) {
    return strtoul(str, endptr, base);
}



#endif