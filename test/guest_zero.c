/* Optional TP_29 probe. Run only on a disposable test disk: stock TOS's
 * zero-length Mshrink can corrupt the memory lists. Raw 16-bit GEMDOS ABI.
 */
extern long gemdos();
int report;

finish(message, status)
char *message;
int status;
{
	long count;
	long result;

	count = 0L;
	while (message[count])
		count++;
	result = gemdos(0x40, report, count, (long)message);
	if (result != count)
		status = 1;
	result = gemdos(0x3e, report);
	if (result != 0L)
		status = 1;
	gemdos(9, (long)message);
	if (status && message[0] == 'P')
		gemdos(9, (long)"FAIL zero-report-io\r\n");
	gemdos(0x4c, status);
}

main()
{
	long first;
	long second;
	long survivor;
	long freed;
	long before;
	long result;
	long handle;
	int round;
	int i;
	char *p;

	handle = gemdos(0x3c, (long)"A:\\ZERO.TXT", 0);
	if (handle < 0L) {
		gemdos(9, (long)"FAIL zero-report-create\r\n");
		gemdos(0x4c, 1);
	}
	report = (int)handle;
	before = gemdos(0x48, -1L);
	if (before <= 0L)
		finish("FAIL zero-free-size\r\n", 1);
	for (round = 0; round < 16; round++) {
		first = gemdos(0x48, 4097L);
		second = gemdos(0x48, 8193L);
		if (first <= 0L || second <= 0L)
			finish("FAIL zero-allocation\r\n", 1);
		/* Alternate freeing the allocated-list head and a non-head entry. */
		freed = (round & 1) ? first : second;
		survivor = (round & 1) ? second : first;
		p = (char *)survivor;
		for (i = 0; i < 4097; i++)
			p[i] = (char)((i + round) & 255);
		result = gemdos(0x4a, 0, freed, 0L);
		if (result != 0L)
			finish("FAIL zero-mshrink\r\n", 1);
		for (i = 0; i < 4097; i++)
			if (p[i] != (char)((i + round) & 255))
				finish("FAIL zero-survivor-data\r\n", 1);
		/* The survivor must still be an allocated block. Direct freeit()
		 * without unlinking the zeroed block loses/corrupts that list.
		 */
		result = gemdos(0x49, survivor);
		if (result != 0L)
			finish("FAIL zero-free-survivor\r\n", 1);
		result = gemdos(0x48, -1L);
		if (result != before)
			finish("FAIL zero-memory-recovery\r\n", 1);
	}
	finish("PASS zero-shrink\r\nDONE\r\n", 0);
}
