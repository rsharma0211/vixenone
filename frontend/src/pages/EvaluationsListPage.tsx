import React from 'react';

export const EvaluationsListPage: React.FC = () => {
  return (
    <div className="space-y-4 text-left">
      <div>
        <h1 className="text-page-title text-text font-semibold tracking-tight">
          Evaluations
        </h1>
        <p className="text-body text-muted">
          Compare vendor proposals against your requirements.
        </p>
      </div>

      <div className="rounded-lg border border-dashed border-border p-12 text-center text-muted text-sm">
        Coming next
      </div>
    </div>
  );
};

export default EvaluationsListPage;
