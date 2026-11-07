/* Small SAS example with invented course references.
   Separate the course reference from its term before loading a reporting table.
   Rows without a '|' are already clean and keep a blank TermCode. */
data work.sample_adoptions;
    length CourseCRN $40 TermCode $6;
    input CourseCRN $char40.;
    CourseCRN = strip(CourseCRN);
    if index(CourseCRN, '|') then do;
        TermCode = strip(scan(CourseCRN, -1, '|'));
        CourseCRN = strip(scan(CourseCRN, 1, '|'));
    end;
    datalines;
12298|202610
15477|202710
18820
;
run;
proc print data=work.sample_adoptions noobs; run;

