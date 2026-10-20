import { useState } from 'react';
import ChatWidget from './ChatWidget';

const FLIGHTS_SEARCH_API_URL = (
  import.meta.env.VITE_FLIGHTS_SEARCH_API_URL || 'http://127.0.0.1:8000'
).replace(/\/$/, '');

const MAJOR_CITIES = [
  "Abu Dhabi", "Auckland", "Amsterdam", "Athens", "Atlanta",
  "Bangkok", "Barcelona", "Beijing", "Berlin", "Bogota", "Boston", "Brussels", "Buenos Aires",
  "Cairo", "Cape Town", "Casablanca", "Chicago", "Copenhagen",
  "Dallas", "Delhi", "Denver", "Doha", "Dubai", "Dublin",
  "Frankfurt", "Geneva", "Hanoi", "Helsinki", "Ho Chi Minh City", "Hong Kong", "Honolulu", "Houston",
  "Istanbul", "Jakarta", "Johannesburg", "Kuala Lumpur",
  "Las Vegas", "Lima", "Lisbon", "London", "Los Angeles",
  "Madrid", "Manila", "Melbourne", "Mexico City", "Miami", "Milan", "Montreal", "Mumbai", "Munich",
  "New York", "Nairobi", "New Delhi", "Oslo",
  "Paris", "Prague", "Reykjavik", "Rio de Janeiro", "Rome",
  "San Francisco", "Santiago", "Sao Paulo", "Seattle", "Seoul", "Shanghai", "Singapore", "Stockholm", "Sydney",
  "Taipei", "Tel Aviv", "Tokyo", "Toronto",
  "Vancouver", "Vienna", "Warsaw", "Washington D.C.", "Zurich"
].sort();

function App() {
  const [searchParams, setSearchParams] = useState({
    origin: 'Paris',
    destination: 'New York',
    departure_date: '2027-03-10',
    return_date: '2027-03-20',
    passengers: 1,
    direct: false,
    max_price: '',
    max_stops: '',
  });

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [flights, setFlights] = useState([]);
  const [currentPage, setCurrentPage] = useState(1);
  const flightsPerPage = 5;

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setSearchParams((prev) => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : (name === 'passengers' ? parseInt(value, 10) : value),
    }));
  };

  const fetchFlights = async (params) => {
    setLoading(true);
    setError(null);
    setFlights([]);
    setCurrentPage(1);

    const payload = {
      origin: params.origin,
      destination: params.destination,
      departure_date: params.departure_date,
      return_date: params.return_date,
      passengers: params.passengers,
      filters: {
        ...(params.direct && { direct: true }),
        ...(params.max_price && { max_price: parseInt(params.max_price, 10) }),
        ...(params.max_stops !== '' && { max_stops: parseInt(params.max_stops, 10) }),
      }
    };

    try {
      const response = await fetch(`${FLIGHTS_SEARCH_API_URL}/run-flights-search`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.status === 'success' && data.results && data.results[0]?.flights) {
        setFlights(data.results[0].flights);
      } else {
        setError('No flights found or invalid response format.');
      }
    } catch (err) {
      setError(`Failed to fetch flights: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    await fetchFlights(searchParams);
  };

  const indexOfLastFlight = currentPage * flightsPerPage;
  const indexOfFirstFlight = indexOfLastFlight - flightsPerPage;
  const currentFlights = flights.slice(indexOfFirstFlight, indexOfLastFlight);
  const totalPages = Math.ceil(flights.length / flightsPerPage);

  const paginate = (pageNumber) => setCurrentPage(pageNumber);

  return (
    <div className="container">
      <header>
        <h1>✈️ Flights Search Simulator</h1>
        <p>Powered by Gemini & Google ADK</p>
      </header>

      <div className="glass-panel search-bar">
        <form onSubmit={handleSearch}>
          <datalist id="cities-list">
            {MAJOR_CITIES.map((city, index) => (
              <option key={index} value={city} />
            ))}
          </datalist>

          <div className="form-group">
            <label>Origin</label>
            <input
              type="text"
              name="origin"
              list="cities-list"
              value={searchParams.origin}
              onChange={handleChange}
              autoComplete="off"
              required
            />
          </div>
          <div className="form-group">
            <label>Destination</label>
            <input
              type="text"
              name="destination"
              list="cities-list"
              value={searchParams.destination}
              onChange={handleChange}
              autoComplete="off"
              required
            />
          </div>
          <div className="form-group">
            <label>Departure Date</label>
            <input type="date" name="departure_date" value={searchParams.departure_date} onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Return Date</label>
            <input type="date" name="return_date" value={searchParams.return_date} onChange={handleChange} required />
          </div>
          <div className="form-group">
            <label>Passengers</label>
            <input type="number" name="passengers" value={searchParams.passengers} onChange={handleChange} min="1" required />
          </div>

          <div className="form-group-checkbox">
            <label className="checkbox-label">
              <input type="checkbox" name="direct" checked={searchParams.direct} onChange={handleChange} />
              Direct Only
            </label>
          </div>

          <div className="form-group">
            <label>Max Price (EUR)</label>
            <input type="number" name="max_price" value={searchParams.max_price} onChange={handleChange} placeholder="e.g. 1000" />
          </div>

          <div className="form-group">
            <label>Max Stops</label>
            <input type="number" name="max_stops" value={searchParams.max_stops} onChange={handleChange} placeholder="e.g. 1" min="0" />
          </div>

          <button type="submit" disabled={loading} className="btn-primary">
            {loading ? 'Searching...' : 'Search Flights'}
          </button>
        </form>
      </div>

      {error && <div className="error-message">{error}</div>}

      <div className="results-container">
        {loading && <div className="loader">Analyzing flight paths...</div>}

        {!loading && flights.length > 0 && (
          <>
            <div className="flights-list">
              {currentFlights.map((flight, idx) => (
                <div key={idx} className="flight-card glass-panel">
                  <div className="flight-airline">
                    <h3>{flight.airline}</h3>
                    <p className="flight-number">{flight.flight_number}</p>
                  </div>
                  <div className="flight-route">
                    <div className="flight-leg">
                      {flight.departure_date && <span className="leg-label">Outbound • {flight.departure_date}</span>}
                      <p className="time">{flight.departure_time} - {flight.arrival_time}</p>
                      <p className="cities">{flight.origin} ➔ {flight.destination}</p>
                    </div>
                    {flight.return_time && flight.return_arrival_time && (
                      <>
                        <div className="route-divider">
                          <div className="dash-line"><span className="plane">✈</span></div>
                        </div>
                        <div className="flight-leg">
                          {flight.return_date && <span className="leg-label">Return • {flight.return_date}</span>}
                          <p className="time">{flight.return_time} - {flight.return_arrival_time}</p>
                          <p className="cities">{flight.destination} ➔ {flight.origin}</p>
                        </div>
                      </>
                    )}
                  </div>
                  <div className="flight-stops">
                    <p className="stops-count">{flight.stops === 0 ? 'Direct' : `${flight.stops} Stop${flight.stops > 1 ? 's' : ''}`}</p>
                    {flight.stopover_cities && flight.stopover_cities.length > 0 && (
                      <p className="stop-cities">{flight.stopover_cities.join(', ')}</p>
                    )}
                  </div>
                  <div className="flight-price">
                    <span className="price">{flight.price}</span>
                  </div>
                </div>
              ))}
            </div>
            {totalPages > 1 && (
              <div className="pagination">
                <button
                  onClick={() => paginate(currentPage - 1)}
                  disabled={currentPage === 1}
                  className="page-btn"
                >
                  Previous
                </button>
                <span className="page-info">
                  Page {currentPage} of {totalPages}
                </span>
                <button
                  onClick={() => paginate(currentPage + 1)}
                  disabled={currentPage === totalPages}
                  className="page-btn"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}

        {!loading && flights.length === 0 && !error && (
          <div className="empty-state">No flights loaded yet. Try searching!</div>
        )}
      </div>
      <ChatWidget flights={flights} setFlights={setFlights} searchParams={searchParams} setSearchParams={setSearchParams} fetchFlights={fetchFlights} setCurrentPage={setCurrentPage} />
    </div>
  );
}

export default App;
