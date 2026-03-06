
import React from 'react';
import ReactDOM from "react-dom/client";
import { HydratedRouter} from "react-router/dom";

console.log("Hydrating client...");

ReactDOM.hydrateRoot(
  document,
  <React.StrictMode>
    <HydratedRouter  />
  </React.StrictMode>
);