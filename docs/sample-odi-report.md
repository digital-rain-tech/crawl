# Crawl — Migration Intelligence Report

**Objects discovered:** 8 mappings, 73 expressions, 11 dependencies

## Executive Summary

| Metric | Count |
|---|---|
| Migration risks | **13** (4 high severity) |
| Contradictions | **0** |
| Orphan datastores | 8 |
| Average complexity score | 31 |

## Migration Risks

### High Severity

- **E - Load Oracle (OLH)**: Cross-platform data movement: HiveMovie → OracleMovie
- **D - Calc Ratings (JSON Flatten)**: Cross-platform data movement: HDFSMovie → HiveMovie
- **F - Calc Sales (Big Data SQL)**: Cross-platform data movement: HiveMovie → OracleMovie
- **A - Load Movies (Sqoop)**: Cross-platform data movement: HiveMovie → OracleMovie

### Medium Severity

- **A - Load Movies (Sqoop)**: Oracle SYSDATE — replace with target-specific date function

### Low Severity

- **E - Load Oracle (OLH)**: No execution history — may be dead code or untested
- **B - Merge Movies (Hive)**: No execution history — may be dead code or untested
- **C - Calc Ratings (Hive - Pig - Spark)**: No execution history — may be dead code or untested
- **D - Calc Ratings (JSON Flatten)**: No execution history — may be dead code or untested
- **F - Calc Sales (Big Data SQL)**: No execution history — may be dead code or untested
- **A - Load Movies (Sqoop)**: No execution history — may be dead code or untested
- **G - Sessionize Data (Pig)**: No execution history — may be dead code or untested
- **Populate movieapp_log_odistage**: No execution history — may be dead code or untested

## Migration Complexity Ranking

Higher score = harder to migrate. Based on expression count, number of sources, cross-platform hops, and KM dependencies.

| Score | Mapping | Sources | Targets | Expressions |
|---|---|---|---|---|
| **53** | G - Sessionize Data (Pig) | HiveMovie.movieapp_log_odistage, HiveMovie.cust | HiveMovie.session_stats | 18 |
| **43** | F - Calc Sales (Big Data SQL) | OracleMovie.CUSTOMER, HiveMovie.movieapp_log_odistage | OracleMovie.ODI_COUNTRY_SALES | 10 |
| **40** | D - Calc Ratings (JSON Flatten) | HDFSMovie.movie_ratings | HiveMovie.movie_rating | 11 |
| **30** | A - Load Movies (Sqoop) | OracleMovie.MOVIE | HiveMovie.movie_updates | 9 |
| **25** | C - Calc Ratings (Hive - Pig - Spark) | HiveMovie.movie, HiveMovie.movieapp_log_odistage | HiveMovie.movie_rating | 6 |
| **24** | B - Merge Movies (Hive) | HiveMovie.movie_updates | HiveMovie.movie | 8 |
| **20** | E - Load Oracle (OLH) | HiveMovie.movie_rating | OracleMovie.ODI_MOVIE_RATING | 4 |
| **16** | Populate movieapp_log_odistage | HiveMovie.movieapp_log_avro | HiveMovie.movieapp_log_odistage | 7 |

## Data Lineage

| Source | Target | Via Mapping |
|---|---|---|
| OracleMovie.MOVIE | HiveMovie.movie_updates | A - Load Movies (Sqoop) |
| HiveMovie.movie_updates | HiveMovie.movie | B - Merge Movies (Hive) |
| HiveMovie.movie | HiveMovie.movie_rating | C - Calc Ratings (Hive - Pig - Spark) |
| HiveMovie.movieapp_log_odistage | HiveMovie.movie_rating | C - Calc Ratings (Hive - Pig - Spark) |
| HDFSMovie.movie_ratings | HiveMovie.movie_rating | D - Calc Ratings (JSON Flatten) |
| HiveMovie.movie_rating | OracleMovie.ODI_MOVIE_RATING | E - Load Oracle (OLH) |
| OracleMovie.CUSTOMER | OracleMovie.ODI_COUNTRY_SALES | F - Calc Sales (Big Data SQL) |
| HiveMovie.movieapp_log_odistage | OracleMovie.ODI_COUNTRY_SALES | F - Calc Sales (Big Data SQL) |
| HiveMovie.movieapp_log_odistage | HiveMovie.session_stats | G - Sessionize Data (Pig) |
| HiveMovie.cust | HiveMovie.session_stats | G - Sessionize Data (Pig) |
| HiveMovie.movieapp_log_avro | HiveMovie.movieapp_log_odistage | Populate movieapp_log_odistage |

## Datastore Analysis

### Terminal Targets (final outputs — never read by another mapping)

- **HiveMovie.session_stats**
- **OracleMovie.ODI_COUNTRY_SALES**
- **OracleMovie.ODI_MOVIE_RATING**

### External Sources (ingested but not produced by any mapping)

- **HDFSMovie.movie_ratings**
- **HiveMovie.cust**
- **HiveMovie.movieapp_log_avro**
- **OracleMovie.CUSTOMER**
- **OracleMovie.MOVIE**

## Mapping Details

### A - Load Movies (Sqoop)

**Complexity: 30** | Sources: OracleMovie.MOVIE | Targets: HiveMovie.movie_updates

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

**Complexity: 24** | Sources: HiveMovie.movie_updates | Targets: HiveMovie.movie

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

**Complexity: 25** | Sources: HiveMovie.movie, HiveMovie.movieapp_log_odistage | Targets: HiveMovie.movie_rating

| Expression |
|---|
| `movie_rating.year = @{R0}` |
| `movie_rating.title = @{R0}` |
| `movie_rating.avg_rating = @{R1}(@{R0})` |
| `movie_rating.movie_id = @{R0}` |
| `AGGREGATE.rating = AVG(@{R0})` |
| `AGGREGATE.movieid = @{R0}` |

### D - Calc Ratings (JSON Flatten)

**Complexity: 40** | Sources: HDFSMovie.movie_ratings | Targets: HiveMovie.movie_rating

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

**Complexity: 20** | Sources: HiveMovie.movie_rating | Targets: OracleMovie.ODI_MOVIE_RATING

| Expression |
|---|
| `MOV_RATING.AVG_RATING = @{R0}` |
| `MOV_RATING.MOVIE_ID = @{R0}` |
| `MOV_RATING.TITLE = @{R0}` |
| `MOV_RATING.YEAR = @{R0}` |

### F - Calc Sales (Big Data SQL)

**Complexity: 43** | Sources: OracleMovie.CUSTOMER, HiveMovie.movieapp_log_odistage | Targets: OracleMovie.ODI_COUNTRY_SALES

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

**Complexity: 53** | Sources: HiveMovie.movieapp_log_odistage, HiveMovie.cust | Targets: HiveMovie.session_stats

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

**Complexity: 16** | Sources: HiveMovie.movieapp_log_avro | Targets: HiveMovie.movieapp_log_odistage

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

*Generated by [Crawl](https://github.com/digital-rain-tech/crawl) v0.1.0*
