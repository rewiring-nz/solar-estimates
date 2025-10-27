INSTALL spatial;
LOAD spatial;

CREATE OR REPLACE TABLE MthHrMatrix (
    id INTEGER PRIMARY KEY,
    description VARCHAR
);

CREATE OR REPLACE TABLE MthHrMatrixHour (
    matrix_id INTEGER,
    month TINYINT,
    hour TINYINT,
    value FLOAT,
    FOREIGN KEY (matrix_id) REFERENCES MthHrMatrix(id)
);

CREATE OR REPLACE TABLE MthHrMatrixMonth (
    matrix_id INTEGER,
    month TINYINT,
    value FLOAT,
    FOREIGN KEY (matrix_id) REFERENCES MthHrMatrix(id)
);

CREATE OR REPLACE TYPE IMPACT AS ENUM ('low', 'medium', 'high');

CREATE OR REPLACE TABLE Scenario(
    id INTEGER PRIMARY KEY,
    description VARCHAR,
    probability INTEGER,
    impactAcceptability IMPACT,
    energyGeneration INTEGER,
    energyUse INTEGER,
    financialResiliance FLOAT,
    FOREIGN KEY (probability) REFERENCES MthHrMatrix(id),
    FOREIGN KEY (energyGeneration) REFERENCES MthHrMatrix(id),
    FOREIGN KEY (energyUse) REFERENCES MthHrMatrix(id)
);
-- Not sure what these are?
-- conditions: [Weather, Temp, MthHrMatrix]

CREATE OR REPLACE TABLE CloudyDayProfile (
    id INTEGER PRIMARY KEY,
    description VARCHAR,
    irradiationProbability FLOAT CHECK (0 <= irradiationProbability AND irradiationProbability <= 1),
    cloudyHourProbability FLOAT CHECK (0 <= cloudyHourProbability AND cloudyHourProbability <= 1),
    cloudyDayProbability FLOAT CHECK (0 <= cloudyDayProbability AND cloudyDayProbability <= 1),
    cloudyWeekProbability FLOAT CHECK (0 <= cloudyDayProbability AND cloudyDayProbability <= 1)
);
-- Which way does ownership go with Region?
-- region:
-- month:

CREATE OR REPLACE TABLE Region(
    id INTEGER PRIMARY KEY,
    description VARCHAR,
    energyGeneration INTEGER,
    energyUse INTEGER,
    weatherProfile INTEGER,
    FOREIGN KEY (energyGeneration) REFERENCES MthHrMatrix(id),
    FOREIGN KEY (energyUse) REFERENCES MthHrMatrix(id),
    FOREIGN KEY (weatherProfile) REFERENCES CloudyDayProfile(id)
);

CREATE OR REPLACE TABLE ScenarioSet(
    region_id INTEGER,
    scenario_id INTEGER,
    FOREIGN KEY (region_id) REFERENCES Region(id),
    FOREIGN KEY (scenario_id) REFERENCES Scenario(id)
);

CREATE OR REPLACE TABLE DigitalSurfaceModel_1x1m (
    id INTEGER PRIMARY KEY,
    description VARCHAR,
    x_y_z GEOMETRY,
    slope FLOAT CHECK (0 <= slope AND slope <= 90),
    azimuth FLOAT CHECK (0 <= azimuth AND azimuth <= 360),
    irradiation INTEGER,
    horizonShade INTEGER,
    localShade INTEGER,
    weatherFactor INTEGER,
    FOREIGN KEY (irradiation) REFERENCES MthHrMatrix(id),
    FOREIGN KEY (horizonShade) REFERENCES MthHrMatrix(id),
    FOREIGN KEY (localShade) REFERENCES MthHrMatrix(id),
    FOREIGN KEY (weatherFactor) REFERENCES MthHrMatrix(id)
);

CREATE OR REPLACE TABLE Battery (
    id INTEGER PRIMARY KEY,
    kWH FLOAT CHECK (kWH >= 0)
);

CREATE OR REPLACE TABLE Panel (
    id INTEGER PRIMARY KEY,
    footprint GEOMETRY,
    slope FLOAT CHECK (0 <= slope AND slope <= 90),
    azimuth FLOAT CHECK (0 <= azimuth AND azimuth <= 360),
    FOREIGN KEY (irradiation) REFERENCES MthHrMatrix(id),
    yearlyValue DECIMAL(18,2),
    irradiation INTEGER
);

CREATE OR REPLACE TABLE RoofSegment(
    id INTEGER PRIMARY KEY,
    footprint GEOMETRY,
    slope FLOAT CHECK (0 <= slope AND slope <= 90),
    azimuth FLOAT CHECK (0 <= azimuth AND azimuth <= 360),
    irradiation INTEGER,
    FOREIGN KEY (irradiation) REFERENCES MthHrMatrix(id)
);

CREATE OR REPLACE TABLE PanelSet(
    roof_id INTEGER,
    panel_id INTEGER,
    FOREIGN KEY (roof_id) REFERENCES RoofSegment(id),
    FOREIGN KEY (panel_id) REFERENCES Panel(id)
);

CREATE OR REPLACE TABLE Building(
    id INTEGER PRIMARY KEY,
    description VARCHAR,
    footprint GEOMETRY,
    energyGeneration INTEGER,
    energyUse INTEGER,
    weatherProfile INTEGER,
    kwSellPrice INTEGER,
    kwBuyPrice INTEGER,
    installCosts DECIMAL(18,2),
    FOREIGN KEY (energyGeneration) REFERENCES MthHrMatrix(id),
    FOREIGN KEY (energyUse) REFERENCES MthHrMatrix(id),
    FOREIGN KEY (weatherProfile) REFERENCES CloudyDayProfile(id),
    FOREIGN KEY (kwSellPrice) REFERENCES MthHrMatrix(id),
    FOREIGN KEY (kwBuyPrice) REFERENCES MthHrMatrix(id)
);
-- These are computed? If so,they should be in a different table.
-- daysSaving: Dollars[]
-- paybackTime: Years + financially Viable: Boolean);

CREATE OR REPLACE TABLE BatterySet(
    building_id INTEGER,
    battery_id INTEGER,
    FOREIGN KEY (building_id) REFERENCES Building(id),
    FOREIGN KEY (battery_id) REFERENCES Battery(id)
);

CREATE OR REPLACE TABLE Roof(
    building_id INTEGER,
    roof_segment_id INTEGER,
    FOREIGN KEY (building_id) REFERENCES Building(id),
    FOREIGN KEY (roof_segment_id) REFERENCES RoofSegment(id)
);

