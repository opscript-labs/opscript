import type { ReactNode } from "react";

type AssessmentMetricProps = {
  icon?: ReactNode;
  label: string;
  children: ReactNode;
};

export function AssessmentMetric({
  icon,
  label,
  children,
}: AssessmentMetricProps) {
  return (
    <div className="assessment-metric">
      {icon ? <span className="assessment-metric__icon">{icon}</span> : null}
      <div>
        <p className="assessment-metric__label">{label}</p>
        {children}
      </div>
    </div>
  );
}
