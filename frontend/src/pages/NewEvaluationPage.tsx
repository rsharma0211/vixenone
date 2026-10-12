import React from 'react';
import { Link } from 'react-router-dom';

export const NewEvaluationPage: React.FC = () => {
  return (
    <div className="space-y-4 text-left">
      <nav className="flex items-center text-xs text-muted">
        <Link to="/evaluations" className="hover:text-text transition-colors">
          Evaluations
        </Link>
        <span className="mx-1.5">/</span>
        <span>New evaluation</span>
      </nav>

      <div>
        <h1 className="text-page-title text-text font-semibold tracking-tight">
          New evaluation
        </h1>
        <p className="text-body text-muted">
          Upload one requirements document and 2–3 vendor proposals.
        </p>
      </div>

      <div className="rounded-lg border border-dashed border-border p-12 text-center text-muted text-sm">
        Coming next
      </div>
    </div>
  );
};

export default NewEvaluationPage;
