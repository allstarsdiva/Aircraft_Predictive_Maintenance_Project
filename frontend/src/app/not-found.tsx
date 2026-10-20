import Link from "next/link";
import { Compass } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, PageBody } from "@/components/shell/page-parts";

export default function NotFound() {
  return (
    <PageBody>
      <Card>
        <EmptyState icon={Compass} title="Page not found">
          <p>The page you asked for does not exist.</p>
          <Button asChild size="sm" className="mt-4">
            <Link href="/">Back to fleet overview</Link>
          </Button>
        </EmptyState>
      </Card>
    </PageBody>
  );
}
