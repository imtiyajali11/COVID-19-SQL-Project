-- COVID-19 Global Impact SQL Portfolio Queries
--
-- Tables expected:
--   covid_deaths
--   covid_vaccinations
--
-- Key rules:
--   1. Exclude rows where continent IS NULL for country rankings.
--   2. Use MAX(total_cases), MAX(total_deaths), and MAX(vaccination totals)
--      because these columns are cumulative.
--   3. Use SUM(new_cases) and SUM(new_deaths) for period totals.

-- 1. Dataset coverage
SELECT
    COUNT(*) AS rows,
    COUNT(DISTINCT iso_code) AS iso_codes,
    COUNT(DISTINCT location) AS locations,
    MIN(date) AS start_date,
    MAX(date) AS end_date,
    SUM(CASE WHEN continent IS NULL THEN 1 ELSE 0 END) AS aggregate_rows
FROM covid_deaths;

-- 2. Global totals from country-level rows
SELECT
    ROUND(SUM(new_cases)) AS total_cases,
    ROUND(SUM(new_deaths)) AS total_deaths,
    ROUND(SUM(new_deaths) * 100.0 / NULLIF(SUM(new_cases), 0), 3) AS death_percentage
FROM covid_deaths
WHERE continent IS NOT NULL;

-- 3. Countries with highest total cases
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

-- 4. Countries with highest infection rate, population above 1 million
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

-- 5. Countries with highest total deaths
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

-- 6. Cases and deaths by continent
SELECT
    continent,
    ROUND(SUM(new_cases)) AS total_cases,
    ROUND(SUM(new_deaths)) AS total_deaths,
    ROUND(SUM(new_deaths) * 100.0 / NULLIF(SUM(new_cases), 0), 2) AS case_fatality_pct
FROM covid_deaths
WHERE continent IS NOT NULL
GROUP BY continent
ORDER BY total_deaths DESC;

-- 7. Highest case fatality rate, countries with at least 1 million cases
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

-- 8. Global daily trend
SELECT
    date,
    SUM(new_cases) AS new_cases,
    SUM(new_deaths) AS new_deaths
FROM covid_deaths
WHERE continent IS NOT NULL
GROUP BY date
ORDER BY date;

-- 9. Highest fully vaccinated share, population above 10 million
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

-- 10. Lowest fully vaccinated share, population above 10 million
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

-- 11. Rolling vaccination doses over time
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
ORDER BY d.location, d.date;

-- 12. Average positive test rate, population above 10 million
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

-- 13. India cumulative impact and vaccination coverage
WITH india_totals AS (
    SELECT
        location,
        MAX(population) AS population,
        MAX(total_cases) AS total_cases,
        MAX(total_deaths) AS total_deaths
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

-- 14. India peak daily cases
SELECT
    date,
    new_cases,
    new_deaths
FROM covid_deaths
WHERE location = 'India'
ORDER BY new_cases DESC
LIMIT 10;

-- 15. Country-level modeling table for correlation or BI dashboard export
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

