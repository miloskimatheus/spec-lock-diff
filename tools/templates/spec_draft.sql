-- Spec-Lock-Diff, Control 4: the aggregate-only queries an agent may run to
-- draft a spec. Every query returns aggregates, never a row of the model. Run
-- them as the agent identity, under the masking of Control 2, with
-- maximum_bytes_billed on the profile, and dry-run each one first (free):
--
--   bq query --use_legacy_sql=false --dry_run < one_query.sql
--
-- Cheapest first: the storage view costs nothing, the rest read one partition.
-- YOU: replace your-project, your_dataset, your_model and the window below.

-- 1. Rows and bytes, from metadata. Free, and enough to write the grain's
--    first draft: how many rows a partition holds is the first number to know.
select table_name, total_rows, total_logical_bytes
from `your-project.your_dataset`.INFORMATION_SCHEMA.TABLE_STORAGE
where table_name = 'your_model';

-- 2. A grain candidate: count(*) against the distinct count of the columns you
--    think identify a row. Equal means a key; APPROX_COUNT_DISTINCT costs a
--    fraction of the exact count and is enough to reject a candidate.
--    YOU: the key columns you are testing, and one recent partition.
select
  count(*) as rows_in_window,
  approx_count_distinct(concat(cast(order_id as string))) as distinct_keys
from `your-project.your_dataset.your_model`
where order_date between date_sub(current_date(), interval 7 day) and current_date();

-- 3. Null rates, per column, for the same window. A column that is never null
--    is a candidate for the key; one that often is, an edge to write down.
--    YOU: one countif per column you care about.
select
  countif(order_id is null) / count(*) as order_id_null_rate,
  countif(customer_id is null) / count(*) as customer_id_null_rate
from `your-project.your_dataset.your_model`
where order_date between date_sub(current_date(), interval 7 day) and current_date();

-- 4. Metric candidates: the sums of the numeric columns over the window. The
--    spec's metrics are the ones a human names from this list.
--    YOU: the numeric columns you would call metrics.
select sum(order_total) as order_total_sum, sum(discount) as discount_sum
from `your-project.your_dataset.your_model`
where order_date between date_sub(current_date(), interval 7 day) and current_date();

-- 5. Edge candidates: the distinct values of a column marked categorical: true,
--    and only those columns. status='cancelled' -> row excluded starts here.
--    YOU: one query per categorical column.
select status, count(*) as rows_with_it
from `your-project.your_dataset.your_model`
where order_date between date_sub(current_date(), interval 7 day) and current_date()
group by status
order by rows_with_it desc;
