select refund_id, gross_revenue from {{ ref('stg_refunds') }}
