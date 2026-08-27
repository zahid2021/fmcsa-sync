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
      <div className="cdl-hero-panel">
        <div className="cdl-shell">
          <header className="cdl-topbar">
            <div className="cdl-topbar-inner">
              <div className="cdl-brand cdl-brand-left">
                <span className="cdl-brand-icon cdl-brand-icon-truck" aria-hidden="true" />
                <div className="cdl-brand-copy">
                  <strong className="cdl-brand-title">
                    CDL <span className="cdl-brand-accent">Data</span> Search
                  </strong>
                  <span className="cdl-brand-tag">FMCSA Carrier Database Search</span>
                </div>
              </div>

              <div className="cdl-brand cdl-brand-right">
                <span className="cdl-brand-icon cdl-brand-icon-fmcsa" aria-hidden="true" />
                <div className="cdl-brand-fmcsa-text">
                  <strong className="cdl-brand-title cdl-brand-title-fmcsa">FMCSA</strong>
                  <div className="cdl-brand-tag-stack">
                    <span>Federal Motor Carrier</span>
                    <span>Safety Administration</span>
                  </div>
                </div>
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
              <svg width="14" height="14" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  d="M15.5 14h-.79l-.28-.27A6.471 6.471 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C8.01 14 6 11.99 6 9.5S8.01 5 10.5 5 15 7.01 15 9.5 12.99 14 10.5 14z"
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
                <svg className="cdl-cal-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    fill="#94a3b8"
                    d="M19 4h-1V2h-2v2H8V2H6v2H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V6a2 2 0 00-2-2zm0 16H5V10h14v10zM5 8V6h14v2H5z"
                  />
                </svg>
              </label>
              <label className="cdl-field cdl-date-wrap">
                <span>End Date</span>
                <input
                  type="text"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  placeholder="yyyy-mm-dd"
                />
                <svg className="cdl-cal-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    fill="#94a3b8"
                    d="M19 4h-1V2h-2v2H8V2H6v2H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V6a2 2 0 00-2-2zm0 16H5V10h14v10zM5 8V6h14v2H5z"
                  />
                </svg>
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

            <div className="cdl-export-range">
              <div className="cdl-export-range-head">
                Export row range (Start / End number)
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
              </div>
            </div>

            <div className="cdl-actions">
              <button
                type="button"
                className="cdl-btn cdl-btn-filter"
                onClick={() => loadData(1, false)}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M4.25 5.61C6.27 8.2 10 13 10 13v6c0 .55.45 1 1 1h2c.55 0 1-.45 1-1v-6s3.72-4.8 5.74-7.39C20.25 4.48 18.67 3 16.75 3H7.25C5.33 3 3.75 4.48 4.25 5.61z" />
                </svg>
                Apply Filter
              </button>
              <button
                type="button"
                className="cdl-btn cdl-btn-download"
                onClick={downloadOneFile}
                disabled={downloadLoading}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
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
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                  <path d="M19 19H5V5h7V3H5a2 2 0 00-2 2v14a2 2 0 002 2h14c1.1 0 2-.9 2-2v-7h-2v7zM14 3v2h3.59l-9.83 9.83 1.41 1.41L19 6.41V10h2V3h-7z" />
                </svg>
                {exportLoading ? "..." : "Export File"}
              </button>
            </div>
          </section>

          <div className="cdl-stats">
            <div className="cdl-stat-card">
              <div className="cdl-stat-icon blue" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm2 16H8v-2h8v2zm0-4H8v-2h8v2zm-3-5V3.5L18.5 9H13z" />
                </svg>
              </div>
              <div>
                <div className="cdl-stat-label">Total Items</div>
                <div className="cdl-stat-value">
                  {Number(totalItems || 0).toLocaleString()}
                </div>
              </div>
            </div>
            <div className="cdl-stat-card">
              <div className="cdl-stat-icon purple" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <path d="M19 3H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zm-7 14H5v-2h7v2zm7-4H5v-2h14v2zm0-4H5V7h14v2z" />
                </svg>
              </div>
              <div>
                <div className="cdl-stat-label">Page</div>
                <div className="cdl-stat-value">
                  {currentPage} / {totalPages || 1}
                </div>
              </div>
            </div>
            <div className="cdl-stat-card">
              <div className="cdl-stat-icon green" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <path d="M3 17v2h6v-2H3zM3 5v2h10V5H3zm10 16v-2h8v-2h-8v-2h-2v6h2zM7 9v2H3v2h4v2h2V9H7zm14 4v-2H11v2h10zm-6-4h2V7h4V5h-4V3h-2v6z" />
                </svg>
              </div>
              <div>
                <div className="cdl-stat-label">Rows</div>
                <div className="cdl-stat-value">{tableData.length}</div>
              </div>
            </div>
            <div className="cdl-stats-promo">
              <div className="cdl-stats-promo-img" aria-hidden="true" />
              <p>
                <span className="promo-line1">Your trusted source for</span>
                <span className="promo-line2">FMCSA carrier data</span>
              </p>
            </div>
          </div>
        </div>
      </div>

      <div className="cdl-body">
        <div className="cdl-shell">
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
                        <th key={column.id}>
                          <span className="cdl-th-inner">
                            {column.label}
                            <span className="cdl-sort" aria-hidden="true">
                              <svg viewBox="0 0 8 5">
                                <path d="M4 0L8 5H0z" />
                              </svg>
                              <svg viewBox="0 0 8 5" style={{ transform: "rotate(180deg)" }}>
                                <path d="M4 0L8 5H0z" />
                              </svg>
                            </span>
                          </span>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {tableData.length === 0 ? (
                      <tr>
                        <td colSpan={Math.max(columns.length, 1)} className="cdl-empty">
                          No data
                        </td>
                      </tr>
                    ) : (
                      tableData.map((row, index) => (
                        <tr key={index}>
                          {columns.map((column) => (
                            <td key={column.id}>
                              {row[column.id] != null ? String(row[column.id]) : ""}
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

          {totalPages > 1 && (
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
          )}

          <footer className="cdl-footer">
            <div className="cdl-footer-left">
              <div className="cdl-footer-shield" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none">
                  <path
                    d="M12 2L4 5.5V11c0 5.1 3.4 9.8 8 11 4.6-1.2 8-5.9 8-11V5.5L12 2z"
                    fill="#3974cc"
                  />
                  <path
                    d="M10.2 13.4L8.5 11.7 7 13.2l3.2 3.2 6.8-6.8-1.5-1.5-4.3 4.3z"
                    fill="#ffffff"
                  />
                </svg>
              </div>
              <span>
                Data provided by FMCSA | Federal Motor Carrier Safety Administration
              </span>
            </div>
            <div className="cdl-footer-right">
              <div className="cdl-footer-truck" aria-hidden="true">
                <img
                  src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAJwAAAB4CAYAAAAHbZvZAAADh0lEQVR4nO3dX0hTYRjH8eM2NSMqLV1ZkGjiRMOE7Cak/3+JlCLoproNIogkuuuiyyK6CaKrsqA/YFGQRFBUF0EhZKCWhSYpjCzUJoZhbusyf4Mcp/KZZ/t+7h7ewznvjo8vP97tbI4DAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD+RlaqJzDbla05Ep9ajwwNyPhwXyv30AVfqieAzELDwRQNB1OBVE8g1QpCjZLRSss3ybg/Vih1SdkiqZ/0tc7QzNITKxxM0XAwRcPBVMZnuHnBUqkH+l5I/X0oKnV57fYZn1M6Y4WDKRoOpmg4mOJ9wCTmr9gu+3Rz5uk+3JeuG9xDF1jhYIqGgykaDqYyfh8umexAjtSBnJw/HPl3CkP7JCN+7b6T1pmQFQ6maDiYouFgigyXRMA/V+qVZRulDrdf/afzL6vYLXV1zSHJdE9vN6RVpmOFgykaDqZoOJgiwyWxtGSd1Ll5K6SuP3BLMteHrocyPtjRPG0G62m/J3Xlql2u5+glrHAwRcPBFA0HU57f46naeUYyVG5enoy/vnvS1Wus3nxOzhdcvlbGo5N6fDxLDndi0XGpx8bfSd1+78S088mvaNDvMnl/3/N/o6lY4WCKhoMpGg6mPLcPV7ntrGQcn18/nzY6EnZ1vpodFzWzLa2V8Zg+lur4E+5Y3IlJ7fPlSh3u6HA1n3TLbIlY4WCKhoMpGg6mPJfhHL/ue3U8OO4q8wRDe+UERcV1Mh6bnNDL+bOlzvInXC4h5P2MRqQe7LyS1pnMLVY4mKLhYIqGg6mMzxfrDz+WTJfj02cYAtm6r5YoHv8h9ds3LVL3t13I6Hu8ZY8+o8EKB1M0HEzRcDDlvX24/+x58xbJWMWrj0rmyCtYLsfHJjWzDYe7pI70tLjKbIsr9btF5i8okvGPLy95OgMWFgWlZoWDKRoOpmg4mPJ0PnAcxwltaJIM1P3svKdeU1ndKZl/QVAzXNuDJk+9nmRY4WCKhoMpGg6mPL8PNz46JnX9/puSiSKRIRmfiA5L3f3k9IxmpCVV+l5iSWirjAd8evnOV9dncjopxwoHUzQcTNFwMOX5DPfp9WUJQf7shfr5K5/+T4186zWY1W+fu67J/PKD5TK/cK/+Pmuk/1Fa7bs1HjzG5+GQOjQcTNFwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGadX8rRqObuYeTtAAAAAElFTkSuQmCC"
                  alt=""
                  width={36}
                  height={28}
                />
              </div>
              <div className="cdl-footer-brand">
                <p className="cdl-footer-title">
                  CDL <span>Data</span> Search
                </p>
                <p className="cdl-footer-tagline">Stay compliant. Stay safe.</p>
              </div>
            </div>
          </footer>
        </div>
      </div>
    </div>
  );
};

export default MainData;
