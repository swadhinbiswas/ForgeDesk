import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [activeTab, setActiveTab] = useState('llm');
  
  return (
    <div className="app-container">
      <header className="app-header">
        <h1>ForgeDesk Flagship Demo</h1>
        <div className="tabs">
          <button 
            className={activeTab === 'llm' ? 'active' : ''} 
            onClick={() => setActiveTab('llm')}
          >
            Local LLM Chat
          </button>
          <button 
            className={activeTab === 'data' ? 'active' : ''} 
            onClick={() => setActiveTab('data')}
          >
            Zero-Copy Data Grid
          </button>
        </div>
      </header>
      
      <main className="app-content">
        {activeTab === 'llm' ? <LLMTab /> : <DataTab />}
      </main>
    </div>
  );
}

function LLMTab() {
  const [modelPath, setModelPath] = useState('');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [modelLoaded, setModelLoaded] = useState(false);

  const selectModel = async () => {
    try {
      const path = await window.__forge__.dialog.open({
        title: "Select GGUF Model",
        filters: [{ name: "Models", extensions: ["gguf"] }]
      });
      if (path) setModelPath(path);
    } catch (e) {
      console.error(e);
    }
  };

  const loadModel = async () => {
    if (!modelPath) return;
    setLoading(true);
    try {
      const res = await window.__forge__.invoke("llm_load", { model_path: modelPath });
      if (res.ok) setModelLoaded(true);
      else alert(res.error);
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  const sendMessage = async () => {
    if (!input || !modelLoaded) return;
    
    const newMessages = [...messages, { role: "user", content: input }];
    setMessages(newMessages);
    setInput('');
    setLoading(true);
    
    try {
      // In a real app, we'd use llm_chat_stream, but keeping it simple for the demo
      const res = await window.__forge__.invoke("llm_chat", { messages: newMessages });
      if (res.ok) {
        setMessages([...newMessages, res.response.choices[0].message]);
      } else {
        alert(res.error);
      }
    } catch (e) {
      console.error(e);
    }
    setLoading(false);
  };

  return (
    <div className="tab-pane">
      <div className="controls">
        <input 
          type="text" 
          value={modelPath} 
          readOnly 
          placeholder="Select a .gguf model file..." 
        />
        <button onClick={selectModel}>Browse</button>
        <button onClick={loadModel} disabled={!modelPath || loading}>
          {loading && !modelLoaded ? "Loading..." : "Load Model"}
        </button>
      </div>
      
      <div className="chat-window">
        <div className="messages">
          {messages.map((msg, i) => (
            <div key={i} className={`message ${msg.role}`}>
              <strong>{msg.role}:</strong> {msg.content}
            </div>
          ))}
        </div>
        <div className="input-area">
          <input 
            type="text" 
            value={input} 
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && sendMessage()}
            disabled={!modelLoaded || loading}
            placeholder="Type a message..."
          />
          <button onClick={sendMessage} disabled={!modelLoaded || loading || !input}>
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

function DataTab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [rows, setRows] = useState(100000);
  
  const generateAndFetch = async () => {
    setLoading(true);
    setError(null);
    setData(null);
    const startTime = performance.now();
    
    try {
      // Step 1: Tell Python to generate the DataFrame and get a memory pointer
      const ptr = await window.__forge__.invoke("generate_dataset", { rows: parseInt(rows) });
      
      if (!ptr.ok) {
        throw new Error(ptr.error);
      }
      
      console.log("Memory pointer received:", ptr);
      
      // Step 2: Fetch the raw binary data directly from Rust via the custom protocol
      const response = await fetch(ptr.url);
      const csvText = await response.text();
      
      // Step 3: Parse a subset for display (don't try to render 100k rows in DOM)
      const lines = csvText.split('\n').slice(0, 101); // Header + 100 rows
      const parsedData = lines.map(line => line.split(','));
      
      const endTime = performance.now();
      setData({
        preview: parsedData,
        totalRows: ptr.rows,
        sizeMB: (csvText.length / (1024 * 1024)).toFixed(2),
        timeMs: (endTime - startTime).toFixed(0)
      });
      
    } catch (e) {
      setError(e.message);
      console.error(e);
    }
    setLoading(false);
  };

  return (
    <div className="tab-pane">
      <div className="controls">
        <label>Rows to generate: </label>
        <input 
          type="number" 
          value={rows} 
          onChange={(e) => setRows(e.target.value)} 
          step="10000"
        />
        <button onClick={generateAndFetch} disabled={loading}>
          {loading ? "Generating & Transferring..." : "Generate Data"}
        </button>
      </div>
      
      {error && <div className="error">Error: {error}</div>}
      
      {data && (
        <div className="data-results">
          <div className="stats-bar">
            <span><strong>Total Rows:</strong> {data.totalRows.toLocaleString()}</span>
            <span><strong>Size:</strong> {data.sizeMB} MB</span>
            <span><strong>Transfer & Parse Time:</strong> {data.timeMs} ms</span>
          </div>
          
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  {data.preview[0].map((h, i) => <th key={i}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {data.preview.slice(1, -1).map((row, i) => (
                  <tr key={i}>
                    {row.map((cell, j) => <td key={j}>{cell}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
            {data.totalRows > 100 && (
              <div className="table-footer">
                Showing 100 of {data.totalRows.toLocaleString()} rows
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
