USE FdaDB;

SELECT * FROM Adverse_Events WHERE safetyreportid = '23353582';
SELECT * FROM Event_Drugs WHERE safetyreportid = '23353582';
SELECT * FROM Event_Reactions WHERE safetyreportid = '23353582';

--DELETE FROM Event_Drugs;
--DELETE FROM Event_Reactions;
--DELETE FROM Adverse_Events;

SELECT
    (SELECT COUNT(*) FROM Adverse_Events)  AS events_count,
    (SELECT COUNT(*) FROM Event_Drugs)     AS drugs_count,
    (SELECT COUNT(*) FROM Event_Reactions) AS reactions_count;

SELECT DB_NAME() AS current_database;