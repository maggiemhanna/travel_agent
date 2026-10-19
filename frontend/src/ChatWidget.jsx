import { useState } from 'react';

function ChatWidget({ flights, setFlights, searchParams, setSearchParams, fetchFlights, setCurrentPage }) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([
    { sender: 'bot', text: 'Hello! I can help you filter or find flights. Try "flights under $500", "flights with good wifi", or "flights with lower emission".' }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const toggleChat = () => setIsOpen(!isOpen);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMessage = input.trim();
    setInput('');
    setMessages((prev) => [...prev, { sender: 'user', text: userMessage }]);
    setLoading(true);

    // Build history from previous messages
    const conversationalHistory = messages.map(m => `${m.sender}: ${m.text}`);

    const payload = {
      user_message: userMessage,
      conversational_history: conversationalHistory,
      flights_input: flights,
      flights_search_input: {
        origin: searchParams.origin,
        destination: searchParams.destination,
        departure_date: searchParams.departure_date,
        return_date: searchParams.return_date,
        passengers: parseInt(searchParams.passengers, 10) || 1
      }
    };

    try {
      const response = await fetch('http://127.0.0.1:8001/run-conversational', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Conversational agent error! status: ${response.status}`);
      }

      const data = await response.json();

      if (data.status === 'success' && data.results) {
        const result = data.results;
        const decision = result.agent_decision;

        if (result.flights_search_output) {
          const updatedParams = {
            ...searchParams,
            ...result.flights_search_output
          };
          setSearchParams(updatedParams);
          if (decision === 'inspiration_agent' && fetchFlights) {
            fetchFlights(updatedParams);
          }
        }

        if (decision === 'filter' || decision === 'filter_smart') {
          // Display agent_response if available
          const botResponse = result.agent_response || "Filters applied!";
          setMessages((prev) => [...prev, { sender: 'bot', text: botResponse }]);

          if (decision === 'filter') {
            // Apply local filter if type and value are provided
            if (result.filter_type && result.filter_value !== undefined) {
              const value = result.filter_value;

              // Update top-level search inputs
              setSearchParams(prev => {
                const updates = {};
                if (result.filter_type === 'price' || result.filter_type === 'max_price') updates.max_price = String(value);
                if (result.filter_type === 'stops' || result.filter_type === 'max_stops') updates.max_stops = String(value);
                if (result.filter_type === 'direct') updates.direct = true;
                return { ...prev, ...updates };
              });

              let filtered = [...flights];
              if (result.filter_type === 'price' || result.filter_type === 'max_price') {
                filtered = flights.filter(f => parseFloat(f.price.replace('$', '')) <= value);
              } else if (result.filter_type === 'stops' || result.filter_type === 'max_stops') {
                filtered = flights.filter(f => f.stops <= value);
              } else if (result.filter_type === 'direct') {
                filtered = flights.filter(f => f.stops === 0);
              }
              setFlights(filtered);
              setCurrentPage(1);
            }
          } else if (decision === 'filter_smart' && result.flights_output) {
            setFlights(result.flights_output);
            setCurrentPage(1);
          }
        } else if (decision === 'continue' || decision === 'inspiration_agent') {
          const botResponse = result.agent_response || (decision === 'inspiration_agent' ? "Here is a new suggestion!" : "I see.");
          setMessages((prev) => [...prev, { sender: 'bot', text: botResponse }]);
        }
      } else {
        setMessages((prev) => [...prev, { sender: 'bot', text: "Sorry, I received an invalid response format." }]);
      }
    } catch (err) {
      setMessages((prev) => [...prev, { sender: 'bot', text: `Failed to connect to agent: ${err.message}` }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Floating Action Button */}
      <button className="chat-fab" onClick={toggleChat}>
        {isOpen ? '❌' : '💬'}
      </button>

      {/* Chat Panel */}
      <div className={`chat-panel glass-panel ${isOpen ? 'open' : ''}`}>
        <div className="chat-header">
          <h3>Chat Assistant</h3>
        </div>

        <div className="chat-body">
          {messages.map((msg, idx) => (
            <div key={idx} className={`chat-message ${msg.sender}`}>
              <div className="message-bubble">{msg.text}</div>
            </div>
          ))}
          {loading && (
            <div className="chat-message bot">
              <div className="message-bubble typing">Typing...</div>
            </div>
          )}
        </div>

        <form onSubmit={handleSubmit} className="chat-footer">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask AI to filter results..."
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            Send
          </button>
        </form>
      </div>
    </>
  );
}

export default ChatWidget;
