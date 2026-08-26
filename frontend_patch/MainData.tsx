/* FRONTEND ONLY - MainData.tsx */
import Pagination from "@mui/material/Pagination";
import CircularProgress from "@mui/material/CircularProgress";
import { useState, useEffect, useMemo } from "react";
import keysData from "../assets/keys.json";
import axios from "axios";
import "./MainData.css";

const API = "http://127.0.0.1:5000";
const PAGE_SIZE = 1000;

const MainData = () => {
  const [tableData, setTableData] = useState<any[]>([]);
  const [filterValue, setFilterValue] = useState("");
  const [filterHeader, setFilterHeader] = useState("");
  const [totalPages, setTotalPages] = useState(0);
  const [totalItems, setTotalItems] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [exportLoading, setExportLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState("");
  const [infoMsg, setInfoMsg] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [slugName, setSlugName] = useState("");
  const [exportStart, setExportStart] = useState("1");
  const [exportRowCount, setExportRowCount] = useState("10000");

  const columns = useMemo(
    () =>
      Object.values(keysData || {}).map((key) => ({
        id: String(key),
        label: String(key),
      })),
    []
  );

  useEffect(() => {
    loadData(1, true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const resolveHeader = (header: string, value: string) => {
    const h = header.trim();
    const v = value.trim();
    if (/^[A-Za-z]{2}$/.test(v) && h.toUpperCase() !== "PHY_ST") {
      return "PHY_ST";
    }
    return h;
  };

  const buildFilterParams = () => {
    let value = filterValue.trim();
    let header = filterHeader.trim();
    if (header && value) {
      header = resolveHeader(header, value);
      if (/^[A-Za-z]{2}$/.test(value)) value = value.toUpperCase();
    }
    const params = new URLSearchParams();
    if (header && value) {
      params.set("filterkey", header);
      params.set("filtervalue", value);
    }
    if (startDate) params.set("start_date", startDate);
    if (endDate) params.set("end_date", endDate);
    return { params };
  };

  const loadData = async (page: number, initial = false) => {
    setErrorMsg("");
    setInfoMsg("");
    let value = filterValue.trim();
    let header = filterHeader.trim();
    const hasDates = Boolean(startDate || endDate);

    if (!initial) {
      if (value && !header && !hasDates) {
        setErrorMsg("Select a header.");
        return;
      }
      if (header && !value && !hasDates) {
        setErrorMsg("Enter a filter value.");
        return;
      }
    }

    if (header && value) {
      const fixed = resolveHeader(header, value);
      if (fixed !== header) {
        header = fixed;
        setFilterHeader("PHY_ST");
        value = value.toUpperCase();
        setFilterValue(value);
      }
    }

    const hasFilter = Boolean(header && value);
    const useAll = initial || (!hasFilter && !hasDates);

    try {
      setLoading(true);
      const params: Record<string, string | number> = {
        page,
        per_page: PAGE_SIZE,
      };
      if (hasFilter) {
        params.filterkey = header;
        params.filtervalue = value;
      }
      if (startDate) params.start_date = startDate;
      if (endDate) params.end_date = endDate;

      const response = await axios.get(useAll ? `${API}/all` : `${API}/filter/`, {
        params: useAll ? { page, per_page: PAGE_SIZE } : params,
        timeout: 120000,
      });

      const rows = response?.data?.data || [];
      const total = Number(
        response?.data?.total_count ?? response?.data?.total ?? 0
      );
      setTableData(rows);
      setTotalItems(total);
      setTotalPages(Math.max(1, Math.ceil(total / PAGE_SIZE) || 1));
      setCurrentPage(page);

      if (!useAll && total === 0) setErrorMsg("No results.");
    } catch (error: any) {
      setTableData([]);
      setTotalItems(0);
      setTotalPages(1);
      const apiErr = error?.response?.data?.error;
      if (apiErr) setErrorMsg(String(apiErr));
      else if (error?.code === "ECONNABORTED") setErrorMsg("Request timed out.");
      else if (error?.code === "ERR_NETWORK" || !error?.response) {
        setErrorMsg("Backend not running (python run.py).");
      } else setErrorMsg("API error.");
    } finally {
      setLoading(false);
    }
  };

  const downloadOneFile = () => {
    const { params } = buildFilterParams();
    if (!params.toString()) {
      setErrorMsg("Apply a filter first.");
      return;
    }
    setErrorMsg("");
    setDownloadLoading(true);
    window.location.href = `${API}/export?${params.toString()}`;
    setTimeout(() => setDownloadLoading(false), 4000);
  };

  const exportToDrive = async () => {
    const slug = slugName.trim();
    if (!slug) {
      setErrorMsg("Enter slug name.");
      return;
    }
    const startRaw = exportStart.trim();
    const countRaw = exportRowCount.trim();
    if (!startRaw || !countRaw) {
      setErrorMsg("Enter start number and row count.");
      return;
    }
    const startNum = parseInt(startRaw, 10);
    const rowCount = parseInt(countRaw, 10);
    if (!Number.isFinite(startNum) || !Number.isFinite(rowCount)) {
      setErrorMsg("Start and row count must be numbers.");
      return;
    }
    if (startNum < 1 || rowCount < 1) {
      setErrorMsg("Start must be >= 1 and row count >= 1.");
      return;
    }
    const endNum = startNum + rowCount - 1;
    if (totalItems > 0 && endNum > totalItems) {
      setErrorMsg(
        `Range ${startNum.toLocaleString()}-${endNum.toLocaleString()} exceeds total (${totalItems.toLocaleString()}).`
      );
      return;
    }
    const { params } = buildFilterParams();
    if (!params.toString()) {
      setErrorMsg("Apply a filter first.");
      return;
    }
    params.set("slug", slug);
    params.set("start_number", String(startNum));
    params.set("row_count", String(rowCount));
    setErrorMsg("");
    setInfoMsg("");
    setExportLoading(true);
    try {
      const res = await axios.get(`${API}/export/drive`, {
        params: Object.fromEntries(params),
        timeout: 600000,
      });
      const data = res.data || {};
      if (data.api_version !== undefined && data.api_version < 3) {
        setErrorMsg(
          "Backend is outdated. Paste latest new_backend.py into run.py and restart."
        );
        return;
      }
      if (data.range_rows !== undefined && data.range_rows > rowCount) {
        setErrorMsg(
          `Backend exported ${data.range_rows} rows but you asked for ${rowCount}. Update run.py.`
        );
        return;
      }
      setInfoMsg(
        "Exported from row " +
          (data.start_number ?? startNum) +
          ", " +
          (data.row_count ?? rowCount).toLocaleString() +
          " rows (through row " +
          (data.end_number ?? endNum).toLocaleString() +
          ") / " +
          (data.chunks ?? 0) +
          " " +
          (data.format || "xlsx") +
          " file(s) -> " +
          (data.folder || data.drive_root || "") +
          (data.note ? " | " + data.note : "")
      );
    } catch (error: any) {
      const apiErr = error?.response?.data?.error;
      const status = error?.response?.status;
      if (apiErr) setErrorMsg(String(apiErr));
      else if (error?.code === "ECONNABORTED") setErrorMsg("Export timed out.");
      else if (error?.code === "ERR_NETWORK" || !error?.response) {
        setErrorMsg("Backend not running (python run.py).");
      } else {
        setErrorMsg(
          "Export failed HTTP " + (status || "") + ". Check /export/drive route."
        );
      }
    } finally {
      setExportLoading(false);
    }
  };

  return (
    <div className="fmcsa-app">
      <div className="fmcsa-bg" aria-hidden="true" />

      <div className="fmcsa-wrap">
        <header className="fmcsa-hero">
          <div className="fmcsa-hero-inner">
            <span className="fmcsa-mark" aria-hidden="true" />
            <div>
              <p className="fmcsa-kicker">Carrier Directory</p>
              <h1 className="fmcsa-title">FMCSA CARRIERS</h1>
            </div>
          </div>
        </header>

        <section className="fmcsa-panel">
          <div className="fmcsa-fields">
            <label className="fmcsa-field">
              <span>Filter value</span>
              <input
                type="text"
                value={filterValue}
                onChange={(e) => {
                  setFilterValue(e.target.value);
                  setCurrentPage(1);
                }}
                placeholder="e.g. TN"
              />
            </label>
            <label className="fmcsa-field">
              <span>Start date</span>
              <input
                type="text"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                placeholder="yyyy-mm-dd"
              />
            </label>
            <label className="fmcsa-field">
              <span>End date</span>
              <input
                type="text"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                placeholder="yyyy-mm-dd"
              />
            </label>
            <label className="fmcsa-field">
              <span>Header</span>
              <select
                value={filterHeader}
                onChange={(e) => setFilterHeader(e.target.value)}
              >
                <option value="">Select header</option>
                {columns.map((column) => (
                  <option key={column.id} value={column.id}>
                    {column.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="fmcsa-field">
              <span>Slug name</span>
              <input
                type="text"
                value={slugName}
                onChange={(e) => setSlugName(e.target.value)}
                placeholder="User name"
              />
            </label>
            <label className="fmcsa-field">
              <span>Start number</span>
              <input
                type="number"
                min={1}
                value={exportStart}
                onChange={(e) => setExportStart(e.target.value)}
                placeholder="e.g. 100001"
              />
            </label>
            <label className="fmcsa-field">
              <span>Row count</span>
              <input
                type="number"
                min={1}
                value={exportRowCount}
                onChange={(e) => setExportRowCount(e.target.value)}
                placeholder="e.g. 10000"
              />
            </label>
          </div>

          <div className="fmcsa-actions">
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => loadData(1, false)}
            >
              Apply Filter
            </button>
            <button
              type="button"
              className="btn btn-download"
              onClick={downloadOneFile}
              disabled={downloadLoading}
            >
              {downloadLoading ? "..." : "Download File"}
            </button>
            <button
              type="button"
              className="btn btn-export"
              onClick={exportToDrive}
              disabled={exportLoading}
            >
              {exportLoading ? "..." : "Export File"}
            </button>
          </div>
        </section>

        <div className="fmcsa-meta">
          <span>
            Total Items: <b>{Number(totalItems || 0).toLocaleString()}</b>
          </span>
          <span>
            Page: <b>{currentPage}</b> / {totalPages || 1}
          </span>
          <span>
            Rows: <b>{tableData.length}</b>
          </span>
        </div>

        {(infoMsg || errorMsg) && (
          <div className="fmcsa-msg">
            {infoMsg ? <p className="ok">{infoMsg}</p> : null}
            {errorMsg ? <p className="err">{errorMsg}</p> : null}
          </div>
        )}

        <div className="fmcsa-table-box">
          {loading ? (
            <div className="fmcsa-loading">
              <CircularProgress size={28} sx={{ color: "#0f766e" }} />
            </div>
          ) : (
            <div className="fmcsa-scroll">
              <table className="fmcsa-table">
                <thead>
                  <tr>
                    {columns.map((column) => (
                      <th key={column.id}>{column.label}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {tableData.length === 0 ? (
                    <tr>
                      <td
                        colSpan={Math.max(columns.length, 1)}
                        className="empty"
                      >
                        No data
                      </td>
                    </tr>
                  ) : (
                    tableData.map((row, index) => (
                      <tr key={index}>
                        {columns.map((column) => (
                          <td key={column.id}>
                            {row[column.id] != null
                              ? String(row[column.id])
                              : ""}
                          </td>
                        ))}
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="fmcsa-pager">
          <Pagination
            count={totalPages || 1}
            page={currentPage}
            onChange={(_e, page) => loadData(page, false)}
            color="primary"
            shape="rounded"
            siblingCount={1}
          />
        </div>
      </div>
    </div>
  );
};

export default MainData;
