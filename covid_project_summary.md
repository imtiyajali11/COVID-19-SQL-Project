# COVID-19 SQL Project Summary

## Project Angle

This project analyzes the global impact of COVID-19 using SQL-style questions:

1. What is the date range and quality of the dataset?
2. What are the global totals for cases and deaths?
3. Which countries had the highest total cases?
4. Which countries had the highest infection rate as a share of population?
5. Which countries had the highest total deaths?
6. Which continents were hit hardest?
7. Which countries had the highest case fatality rate?
8. When did global daily cases and deaths peak?
9. Which countries reached the highest vaccination coverage?
10. Which countries had the lowest vaccination coverage?
11. How did vaccination doses accumulate over time?
12. Which countries had high positive test rates?
13. What does India's COVID timeline look like?
14. Are vaccination, wealth, and health indicators correlated?

## Data Notes

- Death rows: 309,799
- Vaccination rows: 309,799
- Date range: 2020-01-01 to 2023-05-16
- Unique locations: 255
- Country-level locations: 243
- Duplicate `iso_code + date` rows: 0 in both files
- Rows where `continent IS NULL` are aggregates such as World, Asia, Europe, income groups, and the European Union.

## Important SQL Logic

- For country rankings, filter to `continent IS NOT NULL`.
- Use `MAX(total_cases)` and `MAX(total_deaths)` for cumulative country totals.
- Use `SUM(new_cases)` and `SUM(new_deaths)` for global or continent period totals.
- Join deaths and vaccinations on `iso_code` plus `date`.

## Key Findings From This Snapshot

- Global country-level totals are about 765.9 million cases and 6.93 million deaths.
- The global case fatality percentage in the country-level data is about 0.905%.
- The United States has the highest total cases and deaths.
- Europe has the highest total deaths by continent in the country-level aggregation.
- The highest infection-rate rankings are different from total-case rankings because population size matters.
- Among countries with at least 1 million cases, Peru and Mexico have among the highest case fatality rates.
- The global peak daily cases in this snapshot occur in late December 2022, strongly affected by China's reported surge.
- The global peak daily deaths occur on 2021-07-21 in the country-level daily aggregation.
- In India, the largest daily case counts occur in May 2021.
- India's maximum vaccination values in the dataset are about 1.03 billion people vaccinated, 952 million fully vaccinated, and 227 million boosters.

## Suggested Kaggle Storyline

Start with a clean data-quality section, then explain the major SQL decisions. After that, move from global totals to country rankings, then into vaccination progress and India's case study. End with the correlation heatmap and a limitation note that correlation does not prove causation.

## Limitations

- COVID reporting differs across countries.
- Testing availability affects reported case counts and case fatality rates.
- Some columns have high missingness, especially hospital, ICU, booster, and excess mortality fields.
- Latest rows can have missing cumulative values for some countries, so the project uses maximum cumulative values instead of assuming the final date row is complete.

