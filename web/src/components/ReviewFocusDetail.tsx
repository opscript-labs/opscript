type ReviewFocusDetailProps = {
  label: string;
  value: string;
};

export function ReviewFocusDetail({ label, value }: ReviewFocusDetailProps) {
  return (
    <div className="review-focus-detail">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}
