/*Schema for openFDA adverse-event pipeline (FdaDB)
Parent-child model: one adverse_events row per FDA report,
with event_drugs and event_reactions capturing the one-to-many
drug/reaction arrays from the source JSON. Surrogate IDENTITY
keys on the children; safetyreportid (VARCHAR, source-native)
is the natural key on the parent and the FK on both children*/

CREATE DATABASE FdaDB;

CREATE TABLE Adverse_Events(
            safetyreportid varchar(20) PRIMARY KEY,
            receivedate DATE,
            serious varchar(10),
            seriousnessdeath varchar(10),
            seriousnesshospitalization varchar(10),
            primarysourcecountry varchar(10),
            patientonsetage varchar(10),
            patientsex varchar(10)
        );

CREATE TABLE Event_Drugs(
            drug_id INT IDENTITY(1,1) PRIMARY KEY,
            safetyreportid varchar(20) REFERENCES Adverse_Events(safetyreportid),
            medicinalproduct varchar(255),
            activesubstancename varchar(255),
            drugcharacterization varchar(10),
            drugindication varchar(255)
        );

CREATE TABLE Event_Reactions(
            reaction_id INT IDENTITY(1,1) PRIMARY KEY,
            safetyreportid varchar(20) REFERENCES Adverse_Events(safetyreportid),
            reactionmeddrapt varchar(255),
            reactionoutcome varchar(10)
        );
CREATE INDEX idx_event_drugs_reportid ON Event_Drugs(safetyreportid);
CREATE INDEX idx_event_reactions_reportid ON Event_Reactions(safetyreportid);
        
USE FdaDB;
SELECT name from sys.tables;
SELECT name FROM sys.databases;