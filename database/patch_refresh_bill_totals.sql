-- Run against HMS_DB to fix bills incorrectly marked paid when total is zero.
USE HMS_DB;
GO

IF OBJECT_ID('dbo.usp_RefreshBillTotals', 'P') IS NOT NULL
    DROP PROCEDURE dbo.usp_RefreshBillTotals;
GO
CREATE PROCEDURE dbo.usp_RefreshBillTotals
    @bill_id INT
AS
BEGIN
    SET NOCOUNT ON;
    DECLARE @total DECIMAL(12,2) = ISNULL((SELECT SUM(total_price) FROM Bill_Items WHERE bill_id = @bill_id), 0);
    DECLARE @paid DECIMAL(12,2) = ISNULL((SELECT paid_amount FROM Billing WHERE bill_id = @bill_id), 0);
    DECLARE @status NVARCHAR(20) = CASE
        WHEN @total <= 0 THEN 'pending'
        WHEN @paid >= @total THEN 'paid'
        WHEN @paid > 0 THEN 'partial'
        ELSE 'pending'
    END;
    UPDATE Billing SET total_amount = @total, status = @status WHERE bill_id = @bill_id;
    SELECT CAST(1 AS BIT) AS success;
END
GO
