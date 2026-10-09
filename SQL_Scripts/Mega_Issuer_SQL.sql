SELECT t.issuer_id || ' - ' || t3.issuer_name AS Issuer_Title,
        SUM(CASE WHEN t2.months_delinquent <> 0 THEN 1 ELSE 0 END) AS Total_Delinquencies,
        t3.citystate AS Location,
        ROUND(SUM(CASE WHEN t.first_time_home_buyer = 'Y' THEN 1 ELSE 0 END)::NUMERIC/COUNT(*),2)  AS Percent_FTHB,
        ROUND(SUM(CASE WHEN t.down_payment_assistance = 'Y' THEN 1 ELSE 0 END)::NUMERIC/COUNT(*),2)  AS Percent_dpa,
        CASE WHEN t3.subservicer <> 'No Subservicer' THEN t4.subservicer_name ELSE 'No Subservicer' END AS Subservicer
        FROM
        gnma_static_table t
        JOIN mbs_loans_monthly t2 ON t2.disclosure_sequence_number = t.disclosure_sequence_number
        JOIN issuer_info t3 ON t3.issuer_number = t2.issuer_id
        LEFT JOIN subservicers t4 ON t4.subservicer_id = t3.subservicer
        WHERE t3.issuer_group = 'Mega'
        GROUP BY t.issuer_id || ' - ' || t3.issuer_name, t3.citystate, CASE WHEN t3.subservicer <> 'No Subservicer' THEN t4.subservicer_name ELSE 'No Subservicer' END
