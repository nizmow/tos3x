/*
 * guest_child.c - load-and-go child for guest_regress.
 *
 * Allocates one modest block, fills and verifies it, frees it, then
 * Pterm(37).  Any failure terminates with Pterm(1).  K&R C, raw GEMDOS.
 */

extern long gemdos();

main()
{
	long p;
	long r;
	long i;
	char *q;

	p = gemdos(0x48, 4097L);
	if (p <= 0L)
		gemdos(0x4c, 1);

	q = (char *)p;
	for (i = 0L; i < 4097L; i++)
		q[i] = (char)((i * 7L + 19L) & 255L);
	for (i = 0L; i < 4097L; i++) {
		if (q[i] != (char)((i * 7L + 19L) & 255L))
			gemdos(0x4c, 1);
	}

	r = gemdos(0x49, p);
	if (r < 0L)
		gemdos(0x4c, 1);

	gemdos(0x4c, 37);
}
