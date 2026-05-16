# %% [markdown]
# # COVID-19 Global Impact: SQL Portfolio Project
#
# This notebook explores global COVID-19 deaths, cases, testing, and vaccination data.
#
# The workflow is intentionally SQL-first:
#
# 1. Load the two Kaggle CSV files.
# 2. Clean dates and numeric columns.
# 3. Create an in-memory SQLite database.
# 4. Answer real analytical questions using SQL.
# 5. Visualize the most important findings with pandas, matplotlib, and seaborn.
#
# Important data rules:
#
# - `total_cases`, `total_deaths`, and vaccination totals are cumulative. Use `MAX(...)` for country-level totals.
# - `new_cases` and `new_deaths` are daily values. Use `SUM(...)` for period totals.
# - Rows where `continent IS NULL` are aggregate groups such as World, Asia, Europe, or income groups. Exclude them when ranking countries.

# %%
import os
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

try:
    import matplotlib.pyplot as plt
    import seaborn as sns

    HAS_PLOTTING = True
except ImportError:
    HAS_PLOTTING = False
    plt = None
    sns = None

try:
    from IPython.display import display
except ImportError:
    display = print

pd.set_option("display.max_columns", 120)
pd.set_option("display.float_format", lambda value: f"{value:,.2f}")

if HAS_PLOTTING:
    sns.set_theme(style="whitegrid", context="notebook")
    plt.rcParams["figure.figsize"] = (12, 6)

# %% [markdown]
# ## 1. Find and Load the Kaggle Files
#
# Kaggle datasets can sit inside different folder names under `/kaggle/input`.
# This cell searches for the deaths and vaccination CSVs by filename.

# %%
def find_input_csv(keyword: str) -> Path:
    """Find a CSV file below /kaggle/input by keyword, with a local fallback for development."""
    candidates = []

    kaggle_root = Path("/kaggle/input")
    if kaggle_root.exists():
        candidates.extend(kaggle_root.rglob("*.csv"))

    local_root = Path("/Users/alismac/Documents/ITVEDANT/SQL/kaggle/Covid - 19 Impact")
    if local_root.exists():
        candidates.extend(local_root.rglob("*.csv"))

    matches = [path for path in candidates if keyword.lower() in path.name.lower()]
    if not matches:
        raise FileNotFoundError(
            f"Could not find a CSV containing '{keyword}'. Check the Kaggle dataset files."
        )
    return matches[0]


deaths_path = find_input_csv("death")
vaccinations_path = find_input_csv("vacc")

print("Deaths file:", deaths_path)
print("Vaccinations file:", vaccinations_path)

deaths_raw = pd.read_csv(deaths_path)
vaccinations_raw = pd.read_csv(vaccinations_path)

print("Deaths shape:", deaths_raw.shape)
print("Vaccinations shape:", vaccinations_raw.shape)

# %% [markdown]
# ## 2. Clean the Data
#
# We standardize column names, parse dates, and convert numeric-looking columns to numeric types.

# %%
def clean_covid_frame(df: pd.DataFrame) -> pd.DataFrame:
    cleaned = df.copy()
    cleaned.columns = cleaned.columns.str.strip().str.lower()
    date_text = cleaned["date"].astype(str)
    parsed_dates = pd.to_datetime(date_text, format="%m/%d/%Y", errors="coerce")
    missing_dates = parsed_dates.isna()
    if missing_dates.any():
        parsed_dates.loc[missing_dates] = pd.to_datetime(
            date_text.loc[missing_dates], errors="coerce"
        )
    cleaned["date"] = parsed_dates

    text_columns = {"iso_code", "continent", "location", "date", "tests_units"}
    numeric_columns = [column for column in cleaned.columns if column not in text_columns]
    for column in numeric_columns:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")

    return cleaned


deaths = clean_covid_frame(deaths_raw)
vaccinations = clean_covid_frame(vaccinations_raw)

display(deaths.head())
display(vaccinations.head())

# %% [markdown]
# ## 3. Data Quality Snapshot
#
# Before writing analysis queries, check row counts, dates, duplicate keys, and missing values.

# %%
profile = pd.DataFrame(
    {
        "table": ["covid_deaths", "covid_vaccinations"],
        "rows": [len(deaths), len(vaccinations)],
        "columns": [deaths.shape[1], vaccinations.shape[1]],
        "unique_locations": [deaths["location"].nunique(), vaccinations["location"].nunique()],
        "country_locations": [
            deaths.loc[deaths["continent"].notna(), "location"].nunique(),
            vaccinations.loc[vaccinations["continent"].notna(), "location"].nunique(),
        ],
        "start_date": [deaths["date"].min(), vaccinations["date"].min()],
        "end_date": [deaths["date"].max(), vaccinations["date"].max()],
        "duplicate_iso_date_rows": [
            deaths.duplicated(["iso_code", "date"]).sum(),
            vaccinations.duplicated(["iso_code", "date"]).sum(),
        ],
    }
)

display(profile)

aggregate_locations = sorted(deaths.loc[deaths["continent"].isna(), "location"].dropna().unique())
print("Aggregate rows to avoid in country rankings:")
print(aggregate_locations)

# %%
missing_deaths = (
    deaths.isna()
    .mean()
    .mul(100)
    .sort_values(ascending=False)
    .head(12)
    .rename("missing_pct")
    .reset_index()
    .rename(columns={"index": "column"})
)

missing_vaccinations = (
    vaccinations.isna()
    .mean()
    .mul(100)
    .sort_values(ascending=False)
    .head(12)
    .rename("missing_pct")
    .reset_index()
    .rename(columns={"index": "column"})
)

display(missing_deaths)
display(missing_vaccinations)

# %% [markdown]
# ## 4. Create a SQL Database
#
# SQLite lets us run SQL directly inside Kaggle without installing a database server.

# %%
deaths_sql = deaths.copy()
vaccinations_sql = vaccinations.copy()

deaths_sql["date"] = deaths_sql["date"].dt.strftime("%Y-%m-%d")
vaccinations_sql["date"] = vaccinations_sql["date"].dt.strftime("%Y-%m-%d")

conn = sqlite3.connect(":memory:")
deaths_sql.to_sql("covid_deaths", conn, index=False, if_exists="replace")
vaccinations_sql.to_sql("covid_vaccinations", conn, index=False, if_exists="replace")


def run_sql(query: str) -> pd.DataFrame:
    return pd.read_sql_query(query, conn)


def show_sql(title: str, query: str, rows: int = 15) -> pd.DataFrame:
    print(title)
    result = run_sql(query)
    display(result.head(rows))
    return result


show_sql(
    "SQL database coverage",
    """
    SELECT
        COUNT(*) AS rows,
        COUNT(DISTINCT iso_code) AS iso_codes,
        COUNT(DISTINCT location) AS locations,
        MIN(date) AS start_date,
        MAX(date) AS end_date,
        SUM(CASE WHEN continent IS NULL THEN 1 ELSE 0 END) AS aggregate_rows
    FROM covid_deaths;
    """,
)

# %% [markdown]
# ## Question 1: What is the Global COVID Burden?

# %%
global_totals = show_sql(
    "Global totals from country-level rows",
    """
    SELECT
        ROUND(SUM(new_cases)) AS total_cases,
        ROUND(SUM(new_deaths)) AS total_deaths,
        ROUND(SUM(new_deaths) * 100.0 / NULLIF(SUM(new_cases), 0), 3) AS death_percentage
    FROM covid_deaths
    WHERE continent IS NOT NULL;
    """,
)

# %% [markdown]
# ## Question 2: Which Countries Had the Highest Total Cases?

# %%
top_cases = show_sql(
    "Countries with highest total cases",
    """
    WITH country_totals AS (
        SELECT
            continent,
            location,
            MAX(population) AS population,
            MAX(total_cases) AS total_cases,
            MAX(total_deaths) AS total_deaths
        FROM covid_deaths
        WHERE continent IS NOT NULL
        GROUP BY continent, location
    )
    SELECT
        location,
        continent,
        population,
        total_cases,
        total_deaths,
        ROUND(total_cases * 100.0 / NULLIF(population, 0), 2) AS infected_population_pct,
        ROUND(total_deaths * 100.0 / NULLIF(total_cases, 0), 2) AS case_fatality_pct
    FROM country_totals
    ORDER BY total_cases DESC
    LIMIT 15;
    """,
)

# %% [markdown]
# ## Question 3: Which Countries Had the Highest Infection Rate?
#
# This uses `total_cases / population`. A population threshold avoids tiny countries dominating the ranking.

# %%
top_infection_rate = show_sql(
    "Highest infection rate among countries with population above 1 million",
    """
    WITH country_totals AS (
        SELECT
            continent,
            location,
            MAX(population) AS population,
            MAX(total_cases) AS total_cases,
            MAX(total_deaths) AS total_deaths
        FROM covid_deaths
        WHERE continent IS NOT NULL
        GROUP BY continent, location
    )
    SELECT
        location,
        continent,
        population,
        total_cases,
        ROUND(total_cases * 100.0 / NULLIF(population, 0), 2) AS infected_population_pct,
        ROUND(total_deaths * 100.0 / NULLIF(total_cases, 0), 2) AS case_fatality_pct
    FROM country_totals
    WHERE population >= 1000000
    ORDER BY infected_population_pct DESC
    LIMIT 15;
    """,
)

# %% [markdown]
# ## Question 4: Which Countries Had the Highest Death Count?

# %%
top_deaths = show_sql(
    "Countries with highest total deaths",
    """
    WITH country_totals AS (
        SELECT
            continent,
            location,
            MAX(population) AS population,
            MAX(total_cases) AS total_cases,
            MAX(total_deaths) AS total_deaths
        FROM covid_deaths
        WHERE continent IS NOT NULL
        GROUP BY continent, location
    )
    SELECT
        location,
        continent,
        population,
        total_cases,
        total_deaths,
        ROUND(total_deaths * 100000.0 / NULLIF(population, 0), 2) AS deaths_per_100k,
        ROUND(total_deaths * 100.0 / NULLIF(total_cases, 0), 2) AS case_fatality_pct
    FROM country_totals
    ORDER BY total_deaths DESC
    LIMIT 15;
    """,
)

# %% [markdown]
# ## Question 5: Which Continents Were Hit Hardest?
#
# This sums country-level daily rows by continent. It avoids using the aggregate continent rows.

# %%
continent_totals = show_sql(
    "Cases and deaths by continent",
    """
    SELECT
        continent,
        ROUND(SUM(new_cases)) AS total_cases,
        ROUND(SUM(new_deaths)) AS total_deaths,
        ROUND(SUM(new_deaths) * 100.0 / NULLIF(SUM(new_cases), 0), 2) AS case_fatality_pct
    FROM covid_deaths
    WHERE continent IS NOT NULL
    GROUP BY continent
    ORDER BY total_deaths DESC;
    """,
)

# %% [markdown]
# ## Question 6: Which Countries Had the Highest Case Fatality Rate?
#
# We require at least 1 million cases so the ranking focuses on major outbreaks.

# %%
highest_cfr = show_sql(
    "Highest case fatality rate, countries with at least 1 million cases",
    """
    WITH country_totals AS (
        SELECT
            continent,
            location,
            MAX(population) AS population,
            MAX(total_cases) AS total_cases,
            MAX(total_deaths) AS total_deaths
        FROM covid_deaths
        WHERE continent IS NOT NULL
        GROUP BY continent, location
    )
    SELECT
        location,
        continent,
        population,
        total_cases,
        total_deaths,
        ROUND(total_deaths * 100.0 / NULLIF(total_cases, 0), 2) AS case_fatality_pct
    FROM country_totals
    WHERE total_cases >= 1000000
    ORDER BY case_fatality_pct DESC
    LIMIT 15;
    """,
)

# %% [markdown]
# ## Question 7: When Were the Global Peaks in New Cases and New Deaths?

# %%
global_daily = run_sql(
    """
    SELECT
        date,
        SUM(new_cases) AS new_cases,
        SUM(new_deaths) AS new_deaths
    FROM covid_deaths
    WHERE continent IS NOT NULL
    GROUP BY date
    ORDER BY date;
    """
)
global_daily["date"] = pd.to_datetime(global_daily["date"])
global_daily["new_cases_7d"] = global_daily["new_cases"].rolling(7).mean()
global_daily["new_deaths_7d"] = global_daily["new_deaths"].rolling(7).mean()

display(global_daily.sort_values("new_cases", ascending=False).head(10))
display(global_daily.sort_values("new_deaths", ascending=False).head(10))

if HAS_PLOTTING:
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)

    axes[0].plot(global_daily["date"], global_daily["new_cases_7d"], color="#1f77b4")
    axes[0].set_title("Global Daily New Cases, 7-Day Average")
    axes[0].set_ylabel("New cases")

    axes[1].plot(global_daily["date"], global_daily["new_deaths_7d"], color="#d62728")
    axes[1].set_title("Global Daily New Deaths, 7-Day Average")
    axes[1].set_ylabel("New deaths")
    axes[1].set_xlabel("Date")

    plt.tight_layout()
    plt.show()
else:
    print("Plotting libraries are not available in this environment; skipping chart.")

# %% [markdown]
# ## Question 8: Which Countries Reached the Highest Vaccination Coverage?

# %%
top_vaccinated = show_sql(
    "Highest fully vaccinated share among countries with population above 10 million",
    """
    WITH country_vaccination AS (
        SELECT
            d.continent,
            d.location,
            MAX(d.population) AS population,
            MAX(v.people_vaccinated) AS people_vaccinated,
            MAX(v.people_fully_vaccinated) AS people_fully_vaccinated,
            MAX(v.total_boosters) AS total_boosters,
            MAX(v.total_vaccinations) AS total_vaccinations
        FROM covid_deaths d
        JOIN covid_vaccinations v
            ON d.iso_code = v.iso_code
            AND d.date = v.date
        WHERE d.continent IS NOT NULL
        GROUP BY d.continent, d.location
    )
    SELECT
        location,
        continent,
        population,
        people_vaccinated,
        people_fully_vaccinated,
        total_boosters,
        ROUND(people_vaccinated * 100.0 / NULLIF(population, 0), 2) AS vaccinated_pct,
        ROUND(people_fully_vaccinated * 100.0 / NULLIF(population, 0), 2) AS fully_vaccinated_pct,
        ROUND(total_boosters * 100.0 / NULLIF(population, 0), 2) AS booster_pct
    FROM country_vaccination
    WHERE population >= 10000000
        AND people_fully_vaccinated IS NOT NULL
    ORDER BY fully_vaccinated_pct DESC
    LIMIT 20;
    """,
)

low_vaccinated = show_sql(
    "Lowest fully vaccinated share among countries with population above 10 million",
    """
    WITH country_vaccination AS (
        SELECT
            d.continent,
            d.location,
            MAX(d.population) AS population,
            MAX(v.people_vaccinated) AS people_vaccinated,
            MAX(v.people_fully_vaccinated) AS people_fully_vaccinated
        FROM covid_deaths d
        JOIN covid_vaccinations v
            ON d.iso_code = v.iso_code
            AND d.date = v.date
        WHERE d.continent IS NOT NULL
        GROUP BY d.continent, d.location
    )
    SELECT
        location,
        continent,
        population,
        people_vaccinated,
        people_fully_vaccinated,
        ROUND(people_vaccinated * 100.0 / NULLIF(population, 0), 2) AS vaccinated_pct,
        ROUND(people_fully_vaccinated * 100.0 / NULLIF(population, 0), 2) AS fully_vaccinated_pct
    FROM country_vaccination
    WHERE population >= 10000000
        AND people_fully_vaccinated IS NOT NULL
    ORDER BY fully_vaccinated_pct ASC
    LIMIT 20;
    """,
)

# %%
plot_data = top_vaccinated.sort_values("fully_vaccinated_pct", ascending=True)

if HAS_PLOTTING:
    plt.figure(figsize=(12, 8))
    sns.barplot(
        data=plot_data,
        y="location",
        x="fully_vaccinated_pct",
        hue="continent",
        dodge=False,
    )
    plt.title("Highest Fully Vaccinated Share, Countries with Population Above 10 Million")
    plt.xlabel("Fully vaccinated share of population (%)")
    plt.ylabel("")
    plt.legend(title="Continent", bbox_to_anchor=(1.02, 1), loc="upper left")
    plt.tight_layout()
    plt.show()
else:
    print("Plotting libraries are not available in this environment; skipping chart.")

# %% [markdown]
# ## Question 9: How Did Vaccination Doses Accumulate Over Time?
#
# This query uses a SQL window function. It calculates the rolling sum of daily vaccination doses.

# %%
rolling_vaccinations = run_sql(
    """
    SELECT
        d.continent,
        d.location,
        d.date,
        d.population,
        v.new_vaccinations,
        SUM(COALESCE(v.new_vaccinations, 0)) OVER (
            PARTITION BY d.location
            ORDER BY d.date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS rolling_vaccination_doses,
        ROUND(
            SUM(COALESCE(v.new_vaccinations, 0)) OVER (
                PARTITION BY d.location
                ORDER BY d.date
                ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
            ) * 100.0 / NULLIF(d.population, 0),
            2
        ) AS rolling_doses_per_100_people
    FROM covid_deaths d
    JOIN covid_vaccinations v
        ON d.iso_code = v.iso_code
        AND d.date = v.date
    WHERE d.continent IS NOT NULL
        AND d.location IN ('India', 'United States', 'Brazil', 'United Kingdom', 'China')
    ORDER BY d.location, d.date;
    """
)

rolling_vaccinations["date"] = pd.to_datetime(rolling_vaccinations["date"])
display(rolling_vaccinations.tail(10))

if HAS_PLOTTING:
    plt.figure(figsize=(14, 7))
    sns.lineplot(
        data=rolling_vaccinations,
        x="date",
        y="rolling_doses_per_100_people",
        hue="location",
    )
    plt.title("Rolling Vaccination Doses per 100 People")
    plt.xlabel("Date")
    plt.ylabel("Rolling doses per 100 people")
    plt.tight_layout()
    plt.show()
else:
    print("Plotting libraries are not available in this environment; skipping chart.")

# %% [markdown]
# ## Question 10: Which Countries Had the Highest Positive Test Rates?
#
# A high positive rate can indicate a severe outbreak, limited testing, or both.

# %%
testing_positive_rate = show_sql(
    "Average positive test rate among countries with population above 10 million",
    """
    WITH country_testing AS (
        SELECT
            d.continent,
            d.location,
            MAX(d.population) AS population,
            MAX(v.total_tests_per_thousand) AS total_tests_per_thousand,
            AVG(v.positive_rate) AS avg_positive_rate,
            MAX(v.positive_rate) AS max_positive_rate
        FROM covid_deaths d
        JOIN covid_vaccinations v
            ON d.iso_code = v.iso_code
            AND d.date = v.date
        WHERE d.continent IS NOT NULL
        GROUP BY d.continent, d.location
    )
    SELECT
        location,
        continent,
        population,
        total_tests_per_thousand,
        ROUND(avg_positive_rate * 100.0, 2) AS avg_positive_rate_pct,
        ROUND(max_positive_rate * 100.0, 2) AS max_positive_rate_pct
    FROM country_testing
    WHERE population >= 10000000
        AND avg_positive_rate IS NOT NULL
    ORDER BY avg_positive_rate_pct DESC
    LIMIT 20;
    """,
)

# %% [markdown]
# ## Question 11: India Case Study
#
# This is useful if you want to make the project more relevant for an Indian portfolio audience.

# %%
india_summary = show_sql(
    "India cumulative impact",
    """
    WITH india_totals AS (
        SELECT
            location,
            MAX(population) AS population,
            MAX(total_cases) AS total_cases,
            MAX(total_deaths) AS total_deaths,
            MAX(total_cases_per_million) AS total_cases_per_million,
            MAX(total_deaths_per_million) AS total_deaths_per_million
        FROM covid_deaths
        WHERE location = 'India'
        GROUP BY location
    ),
    india_vaccination AS (
        SELECT
            location,
            MAX(people_vaccinated) AS people_vaccinated,
            MAX(people_fully_vaccinated) AS people_fully_vaccinated,
            MAX(total_boosters) AS total_boosters,
            MAX(total_vaccinations) AS total_vaccinations
        FROM covid_vaccinations
        WHERE location = 'India'
        GROUP BY location
    )
    SELECT
        d.location,
        d.population,
        d.total_cases,
        d.total_deaths,
        ROUND(d.total_cases * 100.0 / NULLIF(d.population, 0), 2) AS infected_population_pct,
        ROUND(d.total_deaths * 100.0 / NULLIF(d.total_cases, 0), 2) AS case_fatality_pct,
        v.people_vaccinated,
        v.people_fully_vaccinated,
        v.total_boosters,
        v.total_vaccinations,
        ROUND(v.people_vaccinated * 100.0 / NULLIF(d.population, 0), 2) AS vaccinated_pct,
        ROUND(v.people_fully_vaccinated * 100.0 / NULLIF(d.population, 0), 2) AS fully_vaccinated_pct,
        ROUND(v.total_boosters * 100.0 / NULLIF(d.population, 0), 2) AS booster_pct
    FROM india_totals d
    JOIN india_vaccination v
        ON d.location = v.location;
    """,
)

india_peaks = show_sql(
    "India peak daily cases and deaths",
    """
    SELECT
        date,
        new_cases,
        new_deaths
    FROM covid_deaths
    WHERE location = 'India'
    ORDER BY new_cases DESC
    LIMIT 10;
    """,
)

india_daily = run_sql(
    """
    SELECT
        date,
        new_cases,
        new_deaths
    FROM covid_deaths
    WHERE location = 'India'
    ORDER BY date;
    """
)
india_daily["date"] = pd.to_datetime(india_daily["date"])
india_daily["new_cases_7d"] = india_daily["new_cases"].rolling(7).mean()
india_daily["new_deaths_7d"] = india_daily["new_deaths"].rolling(7).mean()

if HAS_PLOTTING:
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)

    axes[0].plot(india_daily["date"], india_daily["new_cases_7d"], color="#1f77b4")
    axes[0].set_title("India Daily New Cases, 7-Day Average")
    axes[0].set_ylabel("New cases")

    axes[1].plot(india_daily["date"], india_daily["new_deaths_7d"], color="#d62728")
    axes[1].set_title("India Daily New Deaths, 7-Day Average")
    axes[1].set_ylabel("New deaths")
    axes[1].set_xlabel("Date")

    plt.tight_layout()
    plt.show()
else:
    print("Plotting libraries are not available in this environment; skipping chart.")

# %% [markdown]
# ## Question 12: Are Vaccination, Wealth, and Health Indicators Related?
#
# This is an exploratory correlation view. It does not prove causation, but it helps generate discussion.

# %%
country_model = run_sql(
    """
    WITH country_final AS (
        SELECT
            d.continent,
            d.location,
            MAX(d.population) AS population,
            MAX(d.total_cases) AS total_cases,
            MAX(d.total_deaths) AS total_deaths,
            MAX(v.people_fully_vaccinated) AS people_fully_vaccinated,
            MAX(v.total_boosters) AS total_boosters,
            MAX(v.gdp_per_capita) AS gdp_per_capita,
            MAX(v.human_development_index) AS human_development_index,
            MAX(v.median_age) AS median_age,
            MAX(v.hospital_beds_per_thousand) AS hospital_beds_per_thousand,
            MAX(v.life_expectancy) AS life_expectancy
        FROM covid_deaths d
        JOIN covid_vaccinations v
            ON d.iso_code = v.iso_code
            AND d.date = v.date
        WHERE d.continent IS NOT NULL
        GROUP BY d.continent, d.location
    )
    SELECT
        continent,
        location,
        population,
        ROUND(total_cases * 100.0 / NULLIF(population, 0), 2) AS infected_population_pct,
        ROUND(total_deaths * 100000.0 / NULLIF(population, 0), 2) AS deaths_per_100k,
        ROUND(total_deaths * 100.0 / NULLIF(total_cases, 0), 2) AS case_fatality_pct,
        ROUND(people_fully_vaccinated * 100.0 / NULLIF(population, 0), 2) AS fully_vaccinated_pct,
        ROUND(total_boosters * 100.0 / NULLIF(population, 0), 2) AS booster_pct,
        gdp_per_capita,
        human_development_index,
        median_age,
        hospital_beds_per_thousand,
        life_expectancy
    FROM country_final
    WHERE population >= 1000000;
    """
)

display(country_model.head())

corr_columns = [
    "infected_population_pct",
    "deaths_per_100k",
    "case_fatality_pct",
    "fully_vaccinated_pct",
    "booster_pct",
    "gdp_per_capita",
    "human_development_index",
    "median_age",
    "hospital_beds_per_thousand",
    "life_expectancy",
]

corr = country_model[corr_columns].corr(numeric_only=True)

if HAS_PLOTTING:
    plt.figure(figsize=(11, 8))
    sns.heatmap(corr, annot=True, cmap="vlag", center=0, fmt=".2f", linewidths=0.5)
    plt.title("Country-Level Correlation Matrix")
    plt.tight_layout()
    plt.show()
else:
    display(corr)

# %% [markdown]
# ## Final Insights to Write in Your Kaggle Notebook
#
# Use these as your conclusion after running the notebook:
#
# - The United States recorded the highest total cases and deaths in this snapshot.
# - Europe and Asia contributed the largest number of country-level reported cases, while Europe had the highest total deaths by continent in the country-level aggregation.
# - Infection-rate rankings differ from raw case rankings because smaller and medium-sized countries can have a larger share of population infected.
# - Case fatality rate is highest in some countries with large outbreaks such as Peru and Mexico, but CFR depends heavily on testing quality, reporting policy, age structure, and health-system capacity.
# - Vaccination coverage varied widely. Some countries crossed very high fully-vaccinated shares, while several lower-income or conflict-affected countries remained much lower.
# - For India, the sharpest case wave appears in May 2021, and the vaccination rollout reached a large share of the population by the end of the available data.
# - The correlation heatmap is exploratory only. It is good for forming hypotheses, not for claiming causation.
