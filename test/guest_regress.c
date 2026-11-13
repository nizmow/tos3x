/*
 * guest_regress.c - guest-side GEMDOS regression probe.
 *
 * K&R C for Alcyon cc (16-bit int, 32-bit long/pointers).  Raw GEMDOS
 * trap #1 ABI is used directly:
 *
 *   file/process/memory arguments after a WORD selector must be passed as
 *   long so the trap stack layout stays correct; only genuinely word
 *   arguments (selectors, Fopen mode, Fclose handle, Pexec mode, Pterm
 *   code) are passed as int.
 *
 * The PRG is expected at A:\AUTO\REGRESS.PRG, the child at A:\CHILD.PRG,
 * and the report at A:\RESULT.TXT.  The native FAT image is assumed to
 * contain A:\D00..D07\S00..S15\DATA.BIN prepopulated by the harness;
 * this guest only reads that tree.  Every PASS/FAIL/DONE line is also
 * mirrored to the console via Cconws so a real TOS boot can show it.
 * No stdio and no libc startup state are used: main() is entered
 * directly by the harness startup code.
 */

extern long gemdos();

/*
 * Read-only file system tree laid down by the harness:
 *   A:\D<outer>\S<inner>\DATA.BIN
 * byte i is (i + outer * 17 + inner * 3) & 255, file length 257.
 */
#define FS_ROUNDS	3
#define FS_LEAVES	128

#define NBLK		8

int rep_fd;			/* -1 while the report is closed */
char child_tail[4];		/* empty Pexec command tail (and terminator) */
char child_env[4];		/* empty environment: two NULs */

long slen(s)
char *s;
{
	long n;

	n = 0L;
	while (s[n] != 0)
		n++;
	return n;
}

/* Cconws/Cconout mirror, so results are visible on the boot console. */
con_str(s)
char *s;
{
	gemdos(0x09, (long)s);
}

con_ch(c)
int c;
{
	gemdos(0x02, c);
}

/* Every report write must succeed; if it does not, nothing sane is left. */
rep_write(s, n)
char *s;
long n;
{
	long r;

	r = gemdos(0x40, (int)rep_fd, n, (long)s);
	if (r != n) {
		con_str("FAIL fwrite 1\r\n");
		gemdos(0x4c, 1);
	}
}

rep_str(s)
char *s;
{
	rep_write(s, slen(s));
}

/* A complete report fragment goes to both the file and the console. */
say(s)
char *s;
{
	rep_str(s);
	con_str(s);
}

/*
 * Signed decimal conversion without libc arithmetic helpers.  The only
 * values ever printed are GEMDOS return codes and failure indices, so a
 * fixed table of decimal places built by shift/add is sufficient.
 */
rep_num(v)
long v;
{
	char b[16];
	long p[10];
	int i;
	int j;
	int k;
	int d;

	i = 0;
	if (v < 0L) {
		rep_write("-", 1L);
		con_ch('-');
		v = -v;
	}

	p[0] = 1L;
	for (k = 1; k < 10; k++)
		p[k] = (p[k - 1] << 3) + (p[k - 1] << 1);

	k = 9;
	while (k > 0 && p[k] > v)
		k--;
	while (k >= 0) {
		d = 0;
		while (v >= p[k]) {
			v -= p[k];
			d++;
		}
		b[i++] = (char)('0' + d);
		k--;
	}
	j = 0;
	while (j < i) {
		rep_write(&b[j], 1L);
		con_ch(b[j]);
		j++;
	}
}

report_create()
{
	long h;

	h = gemdos(0x3c, (long)"A:\\RESULT.TXT", 0);
	if (h < 0L) {
		con_str("FAIL fcreate 1\r\n");
		gemdos(0x4c, 1);
	}
	rep_fd = (int)h;
}

/* Reopen the report and append; the handle is closed across Pexec. */
report_append()
{
	long h;
	long r;

	h = gemdos(0x3d, (long)"A:\\RESULT.TXT", 2);
	if (h < 0L) {
		con_str("FAIL fopen 1\r\n");
		gemdos(0x4c, 1);
	}
	rep_fd = (int)h;
	r = gemdos(0x42, 0L, (int)rep_fd, 2);
	if (r < 0L) {
		con_str("FAIL fseek 1\r\n");
		gemdos(0x4c, 1);
	}
}

report_close()
{
	long r;

	if (rep_fd < 0)
		return;
	r = gemdos(0x3e, (int)rep_fd);
	rep_fd = -1;
	if (r < 0L) {
		con_str("FAIL fclose 1\r\n");
		gemdos(0x4c, 1);
	}
}

/*
 * Emit "FAIL <op> <value>\r\n", close the report, and terminate nonzero.
 * The report may legitimately be closed here (Pexec section), so reopen
 * it for append first.
 */
fail(op, v)
char *op;
long v;
{
	if (rep_fd < 0)
		report_append();
	say("FAIL ");
	say(op);
	say(" ");
	rep_num(v);
	say("\r\n");
	report_close();
	gemdos(0x4c, 1);
}

/* Deterministic byte pattern keyed by allocation id, offset and cycle. */
fill(p, n, id, cyc)
char *p;
long n;
int id;
int cyc;
{
	long i;
	long e;

	e = ((long)id * 37L + (long)cyc * 53L) & 255L;
	for (i = 0L; i < n; i++) {
		p[i] = (char)e;
		e = (e + 11L) & 255L;
	}
}

/* Returns -1 on success, otherwise the first differing index. */
long check(p, n, id, cyc)
char *p;
long n;
int id;
int cyc;
{
	long i;
	long e;

	e = ((long)id * 37L + (long)cyc * 53L) & 255L;
	for (i = 0L; i < n; i++) {
		if (p[i] != (char)e)
			return i;
		e = (e + 11L) & 255L;
	}
	return -1L;
}

/* Build the directory A:\D<outer>\S<inner> (fixed 8.3 names only). */
mkpath(path, outer, inner)
char *path;
int outer;
int inner;
{
	path[0] = 'A';
	path[1] = ':';
	path[2] = '\\';
	path[3] = 'D';
	path[4] = '0';
	path[5] = (char)('0' + outer);
	path[6] = '\\';
	path[7] = 'S';
	if (inner >= 10) {
		path[8] = '1';
		path[9] = (char)('0' + inner - 10);
	} else {
		path[8] = '0';
		path[9] = (char)('0' + inner);
	}
	path[10] = 0;
}

long launch_child()
{
	/*
	 * An explicit empty environment avoids inheriting a possibly-null
	 * parent environment; all arguments are still passed with GEMDOS
	 * word/long widths (mode word, path/tail/env long).
	 */
	return gemdos(0x4b, 0, (long)"A:\\CHILD.PRG",
		      (long)child_tail, (long)child_env);
}

/* ---------------- memory manager ---------------- */

mem_run()
{
	long blk[NBLK];
	long sizes[NBLK];
	long extra;
	long r;
	long j;
	long recovered;
	int cyc;
	int i;

	sizes[0] = 3L;
	sizes[1] = 9L;
	sizes[2] = 255L;
	sizes[3] = 1000L;
	sizes[4] = 4097L;
	sizes[5] = 16385L;
	sizes[6] = 32769L;
	sizes[7] = 65537L;

	for (cyc = 0; cyc < 8; cyc++) {
		for (i = 0; i < NBLK; i++) {
			blk[i] = gemdos(0x48, sizes[i]);
			if (blk[i] <= 0L)
				fail("malloc", blk[i]);
			fill((char *)blk[i], sizes[i], i, cyc);
		}

		for (i = 0; i < NBLK; i++) {
			j = check((char *)blk[i], sizes[i], i, cyc);
			if (j >= 0L)
				fail("memory", j);
		}

		/* Free alternate blocks and prove the survivors are untouched. */
		for (i = 1; i < NBLK; i += 2) {
			r = gemdos(0x49, blk[i]);
			if (r < 0L)
				fail("free", r);
			blk[i] = 0L;
		}
		for (i = 0; i < NBLK; i += 2) {
			j = check((char *)blk[i], sizes[i], i, cyc);
			if (j >= 0L)
				fail("memory", j);
		}

		/* Extra allocation and free must not disturb the survivors. */
		extra = gemdos(0x48, 12345L);
		if (extra <= 0L)
			fail("malloc", extra);
		fill((char *)extra, 12345L, 50, cyc);
		j = check((char *)extra, 12345L, 50, cyc);
		if (j >= 0L)
			fail("memory", j);
		r = gemdos(0x49, extra);
		if (r < 0L)
			fail("free", r);
		for (i = 0; i < NBLK; i += 2) {
			j = check((char *)blk[i], sizes[i], i, cyc);
			if (j >= 0L)
				fail("memory", j);
		}

		/* Shrink a live block and verify the retained prefix. */
		r = gemdos(0x4a, 0, blk[6], 12345L);
		if (r < 0L)
			fail("mshrink", r);
		j = check((char *)blk[6], 12345L, 6, cyc);
		if (j >= 0L)
			fail("memory", j);
		r = gemdos(0x49, blk[6]);
		if (r < 0L)
			fail("free", r);
		blk[6] = 0L;

		for (i = 0; i < NBLK; i += 2) {
			if (blk[i] != 0L) {
				r = gemdos(0x49, blk[i]);
				if (r < 0L)
					fail("free", r);
			}
		}
		r = gemdos(0x48, -1L);
		if (r <= 0L)
			fail("freeblock", r);
		if (cyc == 0)
			recovered = r;
		else if (r != recovered)
			fail("freeblock", r);
	}

	say("PASS memory\r\n");
}

/* ---------------- process creation ---------------- */

proc_run()
{
	long live;
	long rc;
	long warm;
	long now;
	long r;
	long j;
	int i;

	/* No report handle may be inherited by (or race with) the child. */
	report_close();

	live = gemdos(0x48, 4097L);
	if (live <= 0L)
		fail("malloc", live);
	fill((char *)live, 4097L, 100, 99);
	j = check((char *)live, 4097L, 100, 99);
	if (j >= 0L)
		fail("memory", j);

	/* Warm up one load-and-go, then use it as the free-block baseline. */
	rc = launch_child();
	if (rc != 37L)
		fail("pexec", rc);
	warm = gemdos(0x48, -1L);
	if (warm <= 0L)
		fail("malloc", warm);

	for (i = 0; i < 16; i++) {
		rc = launch_child();
		if (rc != 37L)
			fail("pexec", rc);
		now = gemdos(0x48, -1L);
		if (now != warm)
			fail("freeblock", now);
		j = check((char *)live, 4097L, 100, 99);
		if (j >= 0L)
			fail("memory", j);
	}

	r = gemdos(0x49, live);
	if (r < 0L)
		fail("free", r);

	report_append();
	say("PASS process\r\n");
}

/* ---------------- native file system ---------------- */

fs_run()
{
	char path[24];
	char buf[258];
	long h;
	long n;
	long r;
	long e;
	long j;
	int round;
	int k;
	int idx;
	int outer;
	int inner;

	for (round = 0; round < FS_ROUNDS; round++) {
		for (k = 0; k < FS_LEAVES; k++) {
			idx = (round == 1) ? (FS_LEAVES - 1 - k) : k;
			outer = idx >> 4;
			inner = idx & 15;
			mkpath(path, outer, inner);

			r = gemdos(0x3b, (long)path);
			if (r < 0L)
				fail("dsetpath", r);

			h = gemdos(0x3d, (long)"DATA.BIN", 0);
			if (h < 0L)
				fail("fopen", h);

			n = gemdos(0x3f, (int)h, 258L, (long)buf);
			if (n != 257L)
				fail("fread", n);
			for (j = 0L; j < 257L; j++) {
				e = j + (long)outer * 17L +
				    (long)inner * 3L;
				if (buf[j] != (char)(e & 255L))
					fail("filesystem", j);
			}

			n = gemdos(0x3f, (int)h, 1L, (long)buf);
			if (n != 0L)
				fail("fread", n);

			r = gemdos(0x3e, (int)h);
			if (r < 0L)
				fail("fclose", r);
		}
	}

	r = gemdos(0x3b, (long)"A:\\");
	if (r < 0L)
		fail("dsetpath", r);

	say("PASS filesystem\r\n");
}

main()
{
#ifdef TEST_ZERO_SHRINK
	long zero_result;
#endif
	rep_fd = -1;
	child_tail[0] = 0;
	child_tail[1] = 0;
	child_tail[2] = 0;
	child_tail[3] = 0;
	child_env[0] = 0;
	child_env[1] = 0;
	child_env[2] = 0;
	child_env[3] = 0;

	report_create();
	mem_run();
	proc_run();
	fs_run();

	say("DONE\r\n");
	report_close();
#ifdef TEST_ZERO_SHRINK
	/* Keep the report closed across this child too. Propagate any failure,
	 * including report close errors, rather than trusting AUTO file order.
	 */
	zero_result = gemdos(0x4b, 0, (long)"A:\\ZERO.PRG",
	                     (long)child_tail, (long)child_env);
	if (zero_result != 0L)
		fail("zero-child", zero_result);
#endif
	gemdos(0x4c, 0);
}
