USE FdaDB;

SELECT * FROM Adverse_Events WHERE safetyreportid = '23353582';
SELECT * FROM Event_Drugs WHERE safetyreportid = '23353582';
SELECT * FROM Event_Reactions WHERE safetyreportid = '23353582';

--DELETE FROM Event_Drugs;
--DELETE FROM Event_Reactions;
--DELETE FROM Adverse_Events;

SELECT
    (SELECT COUNT(*) FROM Adverse_Events)  AS events,
    (SELECT COUNT(*) FROM Event_Drugs)     AS drugs,
    (SELECT COUNT(*) FROM Event_Reactions) AS reactions;

SELECT MIN(receivedate) AS earliest, MAX(receivedate) AS latest,
       COUNT(DISTINCT receivedate) AS days_covered
FROM Adverse_Events;



SELECT MIN(receivedate) AS earliest, MAX(receivedate) AS latest,
       COUNT(DISTINCT receivedate) AS days_covered
FROM Adverse_Events;

SELECT session_id, status, blocking_session_id, wait_type, wait_time, total_elapsed_time, command
FROM sys.dm_exec_requests
WHERE session_id > 50
ORDER BY blocking_session_id DESC;

SELECT DB_NAME() AS current_database;