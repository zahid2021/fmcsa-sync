# =============================================================================
# PASTE THIS AT THE VERY BOTTOM of new_backend.py
# (after all other code, BEFORE the line: if __name__ == "__main__":)
# IMPORTANT: NO spaces/tabs before @app.route or def
# =============================================================================

@app.route("/export", methods=["GET"], endpoint="export_csv_v2")
@app.route("/export/", methods=["GET"], endpoint="export_csv_v2_slash")
def export_csv_v2():
    filterkey = request.args.get("filterkey")
    filtervalue = request.args.get("filtervalue")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    try:
        where, params = build_filter_query(
            filterkey, filtervalue, start_date, end_date
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except NameError:
        # if build_filter_query missing, simple equality
        if not filterkey or not filtervalue:
            return jsonify({"error": "filterkey and filtervalue required"}), 400
        where, params = f"`{filterkey}` = %s", [filtervalue]

    connection = get_connection()
    if connection is None:
        return jsonify({"error": "db connection failed"}), 500
    cursor = connection.cursor()
    print(f"[export] WHERE {where} params={params}", flush=True)
    cursor.execute(f"SELECT {SELECT_COLS} FROM {TABLE} WHERE {where}", params)

    col_names = [c.strip() for c in SELECT_COLS.split(",")]
    stem = "carriers"
    if filterkey and filtervalue:
        stem = f"carriers_{filtervalue}"
    filename = f"{stem}_ALL.csv"

    def generate():
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(col_names)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        try:
            while True:
                batch = cursor.fetchmany(2000)
                if not batch:
                    break
                for row in batch:
                    w.writerow(["" if v is None else v for v in row])
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate(0)
        finally:
            cursor.close()
            connection.close()

    return Response(
        generate(),
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-cache",
        },
    )
