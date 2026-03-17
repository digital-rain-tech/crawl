# Crawl — ODI Scan Report

**Source:** oracle/big-data-lite ODI 12c movie demo repository
**Objects discovered:** 8 mappings
**Dependencies:** 11 source→target links

---

## Mappings

### A - Load Movies (Sqoop)

- **Source tables:** OracleMovie.MOVIE
- **Target tables:** HiveMovie.movie_updates
- **Expressions:** 9

| Expression |
|---|
| `movie_updates.ts = SYSDATE` |
| `movie_updates.plot_summary = @{R0}` |
| `movie_updates.movie_id = @{R0}` |
| `movie_updates.budget = @{R0}` |
| `movie_updates.title = @{R0}` |
| `movie_updates.gross = @{R0}` |
| `movie_updates.year = @{R0}` |
| `movie_updates.op = 'I'` |
| `movie_updates.tok = ''` |

### B - Merge Movies (Hive)

- **Source tables:** HiveMovie.movie_updates
- **Target tables:** HiveMovie.movie
- **Expressions:** 8

| Expression |
|---|
| `movie.title = @{R0}` |
| `movie.gross = @{R0}` |
| `movie.year = @{R0}` |
| `movie.movie_id = @{R0}` |
| `movie.plot_summary = @{R0}` |
| `movie.budget = @{R0}` |
| `AGGREGATE.max_ts = max(@{R0})` |
| `AGGREGATE.movie_id = @{R0}` |

### C - Calc Ratings (Hive - Pig - Spark)

- **Source tables:** HiveMovie.movie, HiveMovie.movieapp_log_odistage
- **Target tables:** HiveMovie.movie_rating
- **Expressions:** 6

| Expression |
|---|
| `movie_rating.year = @{R0}` |
| `movie_rating.title = @{R0}` |
| `movie_rating.avg_rating = @{R1}(@{R0})` |
| `movie_rating.movie_id = @{R0}` |
| `AGGREGATE.rating = AVG(@{R0})` |
| `AGGREGATE.movieid = @{R0}` |

### D - Calc Ratings (JSON Flatten)

- **Source tables:** HDFSMovie.movie_ratings
- **Target tables:** HiveMovie.movie_rating
- **Expressions:** 11

| Expression |
|---|
| `movie_rating.movie_id = @{R0}` |
| `movie_rating.year = @{R0}` |
| `movie_rating.title = @{R0}` |
| `movie_rating.avg_rating = @{R1}(@{R0})` |
| `AGGREGATE.movie_id = @{R0}` |
| `AGGREGATE.year = @{R0}` |
| `AGGREGATE.title = @{R0}` |
| `AGGREGATE.avg_rating = AVG(@{R0})` |
| `Flatten.year = @{R0}` |
| `Flatten.title = @{R0}` |
| `Flatten.movie_id = @{R0}` |

### E - Load Oracle (OLH)

- **Source tables:** HiveMovie.movie_rating
- **Target tables:** OracleMovie.ODI_MOVIE_RATING
- **Expressions:** 4

| Expression |
|---|
| `MOV_RATING.AVG_RATING = @{R0}` |
| `MOV_RATING.MOVIE_ID = @{R0}` |
| `MOV_RATING.TITLE = @{R0}` |
| `MOV_RATING.YEAR = @{R0}` |

### F - Calc Sales (Big Data SQL)

- **Source tables:** OracleMovie.CUSTOMER, HiveMovie.movieapp_log_odistage
- **Target tables:** OracleMovie.ODI_COUNTRY_SALES
- **Expressions:** 10

| Expression |
|---|
| `AGGREGATE.CONTINENT_ID = @{R0}` |
| `AGGREGATE.TOTAL_SALES = sum(@{R0})` |
| `AGGREGATE.COUNTRY = @{R0}` |
| `AGGREGATE.COUNTRY_ID = @{R0}` |
| `AGGREGATE.CONTINENT = @{R0}` |
| `CTRY_SALES.TOTAL_SALES = @{R0}` |
| `CTRY_SALES.CONTINENT_ID = @{R0}` |
| `CTRY_SALES.COUNTRY_ID = @{R0}` |
| `CTRY_SALES.CONTINENT = @{R0}` |
| `CTRY_SALES.COUNTRY = @{R0}` |

### G - Sessionize Data (Pig)

- **Source tables:** HiveMovie.movieapp_log_odistage, HiveMovie.cust
- **Target tables:** HiveMovie.session_stats
- **Expressions:** 18

| Expression |
|---|
| `SESSIONIZE.movieid = @{R0}` |
| `SESSIONIZE.time = @{R0}` |
| `SESSIONIZE.custid = @{R0}` |
| `AGGREGATE.country = @{R0}` |
| `AGGREGATE.state_province_id = @{R0}` |
| `AGGREGATE.state_province = @{R0}` |
| `AGGREGATE.max_session = MAX(@{R0})` |
| `AGGREGATE.avg_session = AVG(@{R0})` |
| `AGGREGATE.min_session = MIN(@{R0})` |
| `EXPRESSION.max_session = ROUND(@{R0} * 1000)` |
| `EXPRESSION.avg_session = ROUND(@{R0} * 1000)` |
| `EXPRESSION.min_session = ROUND(@{R0} * 1000)` |
| `session_stats.max_session = @{R0}` |
| `session_stats.avg_session = @{R0}` |
| `session_stats.country = @{R0}` |
| `session_stats.state_province = @{R0}` |
| `session_stats.state_province_id = @{R0}` |
| `session_stats.min_session = @{R0}` |

### Populate movieapp_log_odistage

- **Source tables:** HiveMovie.movieapp_log_avro
- **Target tables:** HiveMovie.movieapp_log_odistage
- **Expressions:** 7

| Expression |
|---|
| `movieapp_log_odistage.rating = @{R0}` |
| `movieapp_log_odistage.recommended = @{R0}` |
| `movieapp_log_odistage.activity = @{R0}` |
| `movieapp_log_odistage.genreid = @{R0}` |
| `movieapp_log_odistage.custid = @{R0}` |
| `movieapp_log_odistage.movieid = @{R0}` |
| `movieapp_log_odistage.time = @{R0}` |

---

## Data Lineage (Dependencies)

| Source | Target | Via Mapping |
|---|---|---|
| OracleMovie.MOVIE | HiveMovie.movie_updates | mapping:A - Load Movies (Sqoop) |
| HiveMovie.movie_updates | HiveMovie.movie | mapping:B - Merge Movies (Hive) |
| HiveMovie.movie | HiveMovie.movie_rating | mapping:C - Calc Ratings (Hive - Pig - Spark) |
| HiveMovie.movieapp_log_odistage | HiveMovie.movie_rating | mapping:C - Calc Ratings (Hive - Pig - Spark) |
| HDFSMovie.movie_ratings | HiveMovie.movie_rating | mapping:D - Calc Ratings (JSON Flatten) |
| HiveMovie.movie_rating | OracleMovie.ODI_MOVIE_RATING | mapping:E - Load Oracle (OLH) |
| OracleMovie.CUSTOMER | OracleMovie.ODI_COUNTRY_SALES | mapping:F - Calc Sales (Big Data SQL) |
| HiveMovie.movieapp_log_odistage | OracleMovie.ODI_COUNTRY_SALES | mapping:F - Calc Sales (Big Data SQL) |
| HiveMovie.movieapp_log_odistage | HiveMovie.session_stats | mapping:G - Sessionize Data (Pig) |
| HiveMovie.cust | HiveMovie.session_stats | mapping:G - Sessionize Data (Pig) |
| HiveMovie.movieapp_log_avro | HiveMovie.movieapp_log_odistage | mapping:Populate movieapp_log_odistage |

---

*Generated by [Crawl](https://github.com/digital-rain-tech/crawl) v0.1.0*
