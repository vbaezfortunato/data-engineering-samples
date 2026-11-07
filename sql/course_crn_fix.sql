/* Split compound course references ("CRN|TERM") into separate columns.

   Some vendor feeds send the course reference number and the six-digit term
   together, e.g. 12298|202610. This script:
     1. saves the term in its own column (so nothing is lost),
     2. trims the CRN,
     3. checks that no compound values remain,
   all inside one transaction.

   It runs on any SQL Server instance: it builds a temporary table with
   invented rows, so no real database is touched. */

SET NOCOUNT ON;

IF OBJECT_ID('tempdb..#BookAdoption') IS NOT NULL DROP TABLE #BookAdoption;

CREATE TABLE #BookAdoption
(
    BookAdoptionID INT IDENTITY(1,1) PRIMARY KEY,
    Source         VARCHAR(20) NOT NULL,
    CourseCRN      VARCHAR(40) NOT NULL,
    TermCode       CHAR(6)     NULL,
    ISBN           VARCHAR(13) NOT NULL   -- stored as text so leading zeros survive
);

INSERT INTO #BookAdoption (Source, CourseCRN, TermCode, ISBN) VALUES
    ('VendorA', '12298|202610', NULL,     '9780000000001'),
    ('VendorA', '15477|202710', NULL,     '0306406152'),
    ('VendorA', '18820',        '202620', '9780000000003'),   -- already clean
    ('VendorB', '20114',        '202630', '9780000000004');   -- other vendor, untouched

SELECT 'Before' AS Stage, * FROM #BookAdoption;

BEGIN TRY
    BEGIN TRANSACTION;

    -- 1. Keep the term before trimming (only when it is a valid 6-digit code)
    UPDATE #BookAdoption
    SET TermCode = SUBSTRING(CourseCRN, CHARINDEX('|', CourseCRN) + 1, 6)
    WHERE Source = 'VendorA'
      AND CHARINDEX('|', CourseCRN) > 0
      AND SUBSTRING(CourseCRN, CHARINDEX('|', CourseCRN) + 1, 40) LIKE '[0-9][0-9][0-9][0-9][0-9][0-9]';

    -- 2. Trim the CRN
    UPDATE #BookAdoption
    SET CourseCRN = LEFT(CourseCRN, CHARINDEX('|', CourseCRN) - 1)
    WHERE Source = 'VendorA'
      AND CHARINDEX('|', CourseCRN) > 0;

    -- 3. Validate: nothing compound left, and every row has a term
    DECLARE @Remaining INT = (SELECT COUNT(*) FROM #BookAdoption WHERE CHARINDEX('|', CourseCRN) > 0);
    DECLARE @NoTerm    INT = (SELECT COUNT(*) FROM #BookAdoption WHERE TermCode IS NULL);

    IF @Remaining > 0 OR @NoTerm > 0
        THROW 50001, 'Validation failed: compound CRNs remain or a term code is missing.', 1;

    COMMIT TRANSACTION;
    PRINT 'Correction committed.';
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    PRINT 'Rolled back: ' + ERROR_MESSAGE();
END CATCH;

SELECT 'After' AS Stage, * FROM #BookAdoption;
