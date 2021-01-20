#include "ud3tn/cmdline.h"
#include "ud3tn/init.h"

#include <stdio.h>

int main(int argc, char *argv[])
{
	// Force line-buffered output. Note: This needs to be done before
	// anything is written to stdout, according to the C99 standard.
	setlinebuf(stdout);
	setlinebuf(stderr);
	init(argc, argv);
	start_tasks(parse_cmdline(argc, argv));
	return start_os();
}
