{{ config(materialized='incremental', unique_key='event_id') }}
select event_id from {{ ref('stg_events') }}
