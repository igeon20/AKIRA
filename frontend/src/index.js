import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

// React의 진입점 (Entry point)
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);