"use client";

import { useEffect, useState } from "react";

/**
 * GeoAI Loader — An animated globe-meets-neural-network visualisation.
 *
 * A pulsing globe with orbiting satellites/nodes, dynamic scan-lines,
 * and neural network connections — representing geomatics data being
 * processed by an AI agent.
 */

const TIPS = [
  "Analyse des couches géospatiales…",
  "Recherche dans les documents…",
  "Consultation du réseau vectoriel…",
  "Triangulation des données SIG…",
  "Extraction des connaissances…",
  "Traitement géomatique en cours…",
  "Indexation des métadonnées…",
  "Corrélation des parcelles…",
];

export function GeoAILoader() {
  const [tipIdx, setTipIdx] = useState(0);
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const interval = setInterval(() => {
      setVisible(false);
      setTimeout(() => {
        setTipIdx((i) => (i + 1) % TIPS.length);
        setVisible(true);
      }, 300);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col items-center gap-5 py-4 select-none">
      {/* Main SVG animation */}
      <div className="relative h-32 w-32">
        <svg
          viewBox="0 0 200 200"
          className="h-full w-full"
          xmlns="http://www.w3.org/2000/svg"
        >
          <defs>
            {/* Gradient for the globe */}
            <radialGradient id="globeGrad" cx="40%" cy="35%" r="60%">
              <stop offset="0%" stopColor="#36acf7" stopOpacity="0.3" />
              <stop offset="50%" stopColor="#0074c6" stopOpacity="0.15" />
              <stop offset="100%" stopColor="#072a49" stopOpacity="0.05" />
            </radialGradient>

            {/* Glow filter */}
            <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feComposite in="SourceGraphic" in2="blur" operator="over" />
            </filter>

            {/* Scan-line gradient */}
            <linearGradient id="scanGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#36acf7" stopOpacity="0" />
              <stop offset="45%" stopColor="#36acf7" stopOpacity="0.4" />
              <stop offset="50%" stopColor="#36acf7" stopOpacity="0.8" />
              <stop offset="55%" stopColor="#36acf7" stopOpacity="0.4" />
              <stop offset="100%" stopColor="#36acf7" stopOpacity="0" />
            </linearGradient>
          </defs>

          {/* Outer pulsing ring */}
          <circle cx="100" cy="100" r="90" fill="none" stroke="#0074c6" strokeWidth="0.5" strokeOpacity="0.3">
            <animate attributeName="r" values="88;92;88" dur="4s" repeatCount="indefinite" />
            <animate attributeName="stroke-opacity" values="0.2;0.5;0.2" dur="4s" repeatCount="indefinite" />
          </circle>

          {/* Globe base */}
          <circle cx="100" cy="100" r="70" fill="url(#globeGrad)" stroke="#0074c6" strokeWidth="1" strokeOpacity="0.4" />

          {/* Latitude lines */}
          {[-35, 0, 35].map((lat, i) => {
            const ry = Math.cos((lat * Math.PI) / 180) * 70;
            return (
              <ellipse
                key={`lat-${i}`}
                cx="100"
                cy={100 - Math.sin((lat * Math.PI) / 180) * 70}
                rx="70"
                ry={ry * 0.3}
                fill="none"
                stroke="#36acf7"
                strokeWidth="0.6"
                strokeOpacity="0.25"
                strokeDasharray="4 6"
              />
            );
          })}

          {/* Longitude lines (rotating) */}
          <g>
            <animateTransform
              attributeName="transform"
              type="rotate"
              from="0 100 100"
              to="360 100 100"
              dur="20s"
              repeatCount="indefinite"
            />
            {[0, 60, 120].map((lon, i) => (
              <ellipse
                key={`lon-${i}`}
                cx="100"
                cy="100"
                rx={Math.cos((lon * Math.PI) / 180) * 20}
                ry="70"
                fill="none"
                stroke="#36acf7"
                strokeWidth="0.6"
                strokeOpacity="0.2"
                strokeDasharray="3 8"
              />
            ))}
          </g>

          {/* Radar scan sweep */}
          <g filter="url(#glow)">
            <animateTransform
              attributeName="transform"
              type="rotate"
              from="0 100 100"
              to="360 100 100"
              dur="3s"
              repeatCount="indefinite"
            />
            <line
              x1="100"
              y1="100"
              x2="100"
              y2="30"
              stroke="#36acf7"
              strokeWidth="1.5"
              strokeOpacity="0.7"
            />
            {/* Sweep trail */}
            <path
              d="M100,100 L100,30 A70,70 0 0,0 55,45 Z"
              fill="#36acf7"
              fillOpacity="0.06"
            />
          </g>

          {/* Orbiting satellite nodes */}
          {[0, 1, 2, 3, 4, 5].map((i) => {
            const dur = 6 + i * 1.5;
            const r = 58 + (i % 3) * 12;
            const startAngle = i * 60;
            return (
              <g key={`sat-${i}`}>
                <animateTransform
                  attributeName="transform"
                  type="rotate"
                  from={`${startAngle} 100 100`}
                  to={`${startAngle + 360} 100 100`}
                  dur={`${dur}s`}
                  repeatCount="indefinite"
                />
                {/* Node */}
                <circle
                  cx={100 + r}
                  cy="100"
                  r="3"
                  fill="#36acf7"
                  fillOpacity="0.9"
                >
                  <animate
                    attributeName="r"
                    values="2;3.5;2"
                    dur={`${1.5 + i * 0.3}s`}
                    repeatCount="indefinite"
                  />
                  <animate
                    attributeName="fill-opacity"
                    values="0.6;1;0.6"
                    dur={`${1.5 + i * 0.3}s`}
                    repeatCount="indefinite"
                  />
                </circle>
                {/* Connection line to center */}
                <line
                  x1="100"
                  y1="100"
                  x2={100 + r}
                  y2="100"
                  stroke="#36acf7"
                  strokeWidth="0.4"
                  strokeOpacity="0.15"
                  strokeDasharray="2 4"
                />
              </g>
            );
          })}

          {/* Neural network data points on globe surface */}
          {[
            [78, 65], [120, 85], [90, 120], [130, 60], [65, 95],
            [115, 130], [80, 45], [140, 100], [60, 75], [110, 55],
          ].map(([cx, cy], i) => (
            <circle
              key={`node-${i}`}
              cx={cx}
              cy={cy}
              r="1.5"
              fill="#7cc8fb"
              fillOpacity="0.8"
            >
              <animate
                attributeName="fill-opacity"
                values="0.3;1;0.3"
                dur={`${2 + (i % 3)}s`}
                begin={`${i * 0.4}s`}
                repeatCount="indefinite"
              />
              <animate
                attributeName="r"
                values="1;2.5;1"
                dur={`${2 + (i % 3)}s`}
                begin={`${i * 0.4}s`}
                repeatCount="indefinite"
              />
            </circle>
          ))}

          {/* Pulsing neural connections between random nodes */}
          {[
            [78, 65, 120, 85],
            [120, 85, 130, 60],
            [90, 120, 115, 130],
            [65, 95, 80, 45],
            [110, 55, 140, 100],
            [80, 45, 130, 60],
            [65, 95, 90, 120],
          ].map(([x1, y1, x2, y2], i) => (
            <line
              key={`conn-${i}`}
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              stroke="#36acf7"
              strokeWidth="0.6"
              strokeOpacity="0.2"
            >
              <animate
                attributeName="stroke-opacity"
                values="0.05;0.35;0.05"
                dur={`${1.5 + (i % 4) * 0.5}s`}
                begin={`${i * 0.3}s`}
                repeatCount="indefinite"
              />
            </line>
          ))}

          {/* Center AI core */}
          <circle cx="100" cy="100" r="8" fill="#0074c6" fillOpacity="0.3">
            <animate attributeName="r" values="6;10;6" dur="2s" repeatCount="indefinite" />
            <animate attributeName="fill-opacity" values="0.2;0.5;0.2" dur="2s" repeatCount="indefinite" />
          </circle>
          <circle cx="100" cy="100" r="4" fill="#36acf7" fillOpacity="0.8">
            <animate attributeName="fill-opacity" values="0.6;1;0.6" dur="1.5s" repeatCount="indefinite" />
          </circle>

          {/* Hexagonal grid overlay (geo feel) */}
          <g strokeOpacity="0.08" stroke="#36acf7" strokeWidth="0.5" fill="none">
            <polygon points="100,55 120,67 120,88 100,100 80,88 80,67" />
            <polygon points="100,100 120,112 120,133 100,145 80,133 80,112" />
            <polygon points="60,78 80,67 80,88 60,100 40,88 40,67">
              <animate attributeName="stroke-opacity" values="0.05;0.15;0.05" dur="3s" repeatCount="indefinite" />
            </polygon>
            <polygon points="140,78 160,67 160,88 140,100 120,88 120,67">
              <animate attributeName="stroke-opacity" values="0.05;0.15;0.05" dur="3s" begin="1.5s" repeatCount="indefinite" />
            </polygon>
          </g>
        </svg>

        {/* Outer glow ring (CSS) */}
        <div className="absolute inset-0 rounded-full animate-ping opacity-[0.08] bg-brand-400" style={{ animationDuration: "3s" }} />
      </div>

      {/* Rotating tip text */}
      <div className="h-6 flex items-center justify-center">
        <p
          className={`text-sm font-medium text-brand-500 dark:text-brand-400 transition-all duration-300 ${
            visible ? "opacity-100 translate-y-0" : "opacity-0 translate-y-2"
          }`}
        >
          {TIPS[tipIdx]}
        </p>
      </div>

      {/* Progress dots */}
      <div className="flex gap-1.5">
        {[0, 1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className="h-1.5 w-1.5 rounded-full bg-brand-400 dark:bg-brand-500"
            style={{
              animation: `pulse 1.5s ease-in-out ${i * 0.2}s infinite`,
              opacity: 0.3,
            }}
          />
        ))}
      </div>
    </div>
  );
}
