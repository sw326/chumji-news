import { fetchPostsPage } from "@/lib/data";
import NewsBoardClient from "@/components/NewsBoardClient";

export const dynamic = "force-dynamic";

export default async function Home() {
  const { posts, hasMore, nextCursor, error } = await fetchPostsPage(null, "all");
  return <NewsBoardClient initialPosts={posts} initialHasMore={hasMore} initialCursor={nextCursor} initialError={error} />;
}
