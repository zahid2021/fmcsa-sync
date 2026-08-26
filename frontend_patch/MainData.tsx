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
  const [exportEnd, setExportEnd] = useState("10000");

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
    const endRaw = exportEnd.trim();
    if (!startRaw || !endRaw) {
      setErrorMsg("Enter start number and end number.");
      return;
    }
    const startNum = parseInt(startRaw, 10);
    const endNum = parseInt(endRaw, 10);
    if (!Number.isFinite(startNum) || !Number.isFinite(endNum)) {
      setErrorMsg("Start and end must be numbers.");
      return;
    }
    if (startNum < 1 || endNum < startNum) {
      setErrorMsg("Start must be >= 1 and end must be >= start.");
      return;
    }
    const rowCount = endNum - startNum + 1;
    if (totalItems > 0 && endNum > totalItems) {
      setErrorMsg(
        `End ${endNum.toLocaleString()} exceeds total (${totalItems.toLocaleString()}).`
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
    params.set("end_number", String(endNum));
    setErrorMsg("");
    setInfoMsg("");
    setExportLoading(true);
    try {
      const res = await axios.get(`${API}/export/drive`, {
        params: Object.fromEntries(params),
        timeout: 600000,
      });
      const data = res.data || {};
      if (!data.api_version || data.api_version < 4) {
        setErrorMsg(
          "Backend outdated (no slice export). Paste new_backend.py, copy to run.py, restart Flask."
        );
        return;
      }
      if (data.start_number === undefined || data.end_number === undefined) {
        setErrorMsg("Backend did not apply start/end range. Update run.py on RDP.");
        return;
      }
      if (data.range_rows !== undefined && data.range_rows > rowCount) {
        setErrorMsg(
          `Exported ${data.range_rows} rows but you asked for ${rowCount}. Update run.py.`
        );
        return;
      }
      setInfoMsg(
        "Exported rows " +
          (data.start_number ?? startNum) +
          "-" +
          (data.end_number ?? endNum) +
          " (" +
          (data.range_rows ?? 0) +
          " rows / " +
          (data.chunks ?? 0) +
          " " +
          (data.format || "xlsx") +
          " file(s)) -> " +
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
    <div className="cdl-app">
      <div className="cdl-shell">
        <div className="cdl-hero-block">
          <header className="cdl-topbar">
            <div className="cdl-brand">
              <div className="cdl-brand-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path d="M18 18.5a1.5 1.5 0 01-3 0 1.5 1.5 0 013 0m1.5-9h-5V7H6v2.5H4.5L3 12v5h1.05a2.5 2.5 0 014.9 0H15a2.5 2.5 0 014.9 0H21v-4.5M6 18.5a1.5 1.5 0 01-3 0 1.5 1.5 0 013 0M5 11h11V9H8V7h7v4" />
                </svg>
              </div>
              <div>
                <p className="cdl-brand-title">CDL Data Search</p>
                <p className="cdl-brand-sub">FMCSA Carrier Database Search</p>
              </div>
            </div>
            <div className="cdl-fmcsa-logo">
              <div className="cdl-fmcsa-text">
                <strong>FMCSA</strong>
                Federal Motor Carrier
                <br />
                Safety Administration
              </div>
              <div className="cdl-fmcsa-shield" aria-hidden="true">
                FMCSA
              </div>
            </div>
          </header>

          <div className="cdl-hero-text">
            <h1>
              Search. Find. <span>Drive Safe.</span>
            </h1>
            <p>
              Access FMCSA motor carrier data and compliance information with ease.
            </p>
          </div>

          <section className="cdl-filters">
            <div className="cdl-filters-head">
              <svg width="13" height="13" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M10 18h4v-2h-4v2ZM3 6v2h18V6H3zm3 7h12v-2H6v2z"
                  fill="currentColor"
                />
              </svg>
              Search Filters
            </div>

            <div className="cdl-fields-main">
              <label className="cdl-field">
                <span>Filter Value</span>
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
              <label className="cdl-field cdl-date-wrap">
                <span>Start Date</span>
                <input
                  type="text"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  placeholder="yyyy-mm-dd"
                />
              </label>
              <label className="cdl-field cdl-date-wrap">
                <span>End Date</span>
                <input
                  type="text"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  placeholder="yyyy-mm-dd"
                />
              </label>
              <label className="cdl-field">
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
              <label className="cdl-field">
                <span>Slug Name</span>
                <input
                  type="text"
                  value={slugName}
                  onChange={(e) => setSlugName(e.target.value)}
                  placeholder="User name"
                />
              </label>
            </div>

            <div className="cdl-fields-export">
              <label className="cdl-field">
                <span>Start Number</span>
                <input
                  type="number"
                  min={1}
                  value={exportStart}
                  onChange={(e) => setExportStart(e.target.value)}
                  placeholder="e.g. 1"
                />
              </label>
              <label className="cdl-field">
                <span>End Number</span>
                <input
                  type="number"
                  min={1}
                  value={exportEnd}
                  onChange={(e) => setExportEnd(e.target.value)}
                  placeholder="e.g. 10000"
                />
              </label>
              <div className="cdl-field" aria-hidden="true" />
              <div className="cdl-field" aria-hidden="true" />
              <div className="cdl-field" aria-hidden="true" />
            </div>

            <div className="cdl-actions">
              <button
                type="button"
                className="cdl-btn cdl-btn-filter"
                onClick={() => loadData(1, false)}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M10 18h4v-2h-4v2ZM3 6v2h18V6H3zm3 7h12v-2H6v2z" />
                </svg>
                Apply Filter
              </button>
              <button
                type="button"
                className="cdl-btn cdl-btn-download"
                onClick={downloadOneFile}
                disabled={downloadLoading}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M19 9h-4V3H9v6H5l7 7 7-7zM5 18v2h14v-2H5z" />
                </svg>
                {downloadLoading ? "..." : "Download File"}
              </button>
              <button
                type="button"
                className="cdl-btn cdl-btn-export"
                onClick={exportToDrive}
                disabled={exportLoading}
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M19 19H5V5h7V3H5a2 2 0 00-2 2v14a2 2 0 002 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z" />
                </svg>
                {exportLoading ? "..." : "Export File"}
              </button>
            </div>
          </section>
        </div>

        <div className="cdl-stats">
          <div className="cdl-stat">
            <span className="cdl-stat-ico doc">📄</span>
            <span>
              Total Items: <b>{Number(totalItems || 0).toLocaleString()}</b>
            </span>
          </div>
          <div className="cdl-stat">
            <span className="cdl-stat-ico page">📑</span>
            <span>
              Page: <b>{currentPage}</b> / {totalPages || 1}
            </span>
          </div>
          <div className="cdl-stat">
            <span className="cdl-stat-ico rows">▦</span>
            <span>
              Rows: <b>{tableData.length}</b>
            </span>
          </div>
          <div className="cdl-stats-promo">
            <div className="cdl-stats-promo-thumb" aria-hidden="true" />
            Your trusted source for FMCSA carrier data
          </div>
        </div>

        {(infoMsg || errorMsg) && (
          <div className="cdl-msg">
            {infoMsg ? <p className="ok">{infoMsg}</p> : null}
            {errorMsg ? <p className="err">{errorMsg}</p> : null}
          </div>
        )}

        <div className="cdl-table-box">
          {loading ? (
            <div className="cdl-loading">
              <CircularProgress size={28} sx={{ color: "#3b82f6" }} />
            </div>
          ) : (
            <div className="cdl-scroll">
              <table className="cdl-table">
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
                        className="cdl-empty"
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

        <div className="cdl-pager">
          <Pagination
            count={totalPages || 1}
            page={currentPage}
            onChange={(_e, page) => loadData(page, false)}
            color="primary"
            shape="rounded"
            siblingCount={1}
          />
        </div>

        <footer className="cdl-footer">
          <span>
            🛡 Data provided by <strong>FMCSA</strong> | Federal Motor Carrier
            Safety Administration
          </span>
          <span>
            <strong>CDL Data Search</strong> — Stay compliant. Stay safe.
          </span>
        </footer>
      </div>
    </div>
  );
};

export default MainData;
