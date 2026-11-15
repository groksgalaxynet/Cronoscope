# Letter from the Creator — Part 2

This journey started in 2025 when I found out about NASA Space Apps Challenge online.

I scrambled and built something for an event I was really excited about. Unfortunately, I tried submitting late and missed the window.

I spent most of 2026 testing different pipelines against astronomical archives and data services like Gaia, MAST, and several others. I tested data provenance to make sure we were looking at real data from legitimate sources and weren't accidentally misrepresenting anything along the way.

Then I started looking at different ways to explore that data.

That work belonged to an earlier project. Only the concepts and methodologies carried over into Cronoscope.

Mind you, I had very little knowledge of what it actually takes to enter this competition. This is my first time attempting something like this.

But I had a new AI sidekick and a curiosity for testing things I didn't understand.

So it began.

About a month before the competition, I set a reminder to check NASA Space Apps Challenge every other day.

I didn't understand much when I signed up, but I knew I wanted to do it.

So I poked the bear.

I started testing pipelines against SPHEREx datasets to see what data was available to explore. I found usable datasets and began implementing what I could.

I needed help understanding what we actually had, what type of data it was, what it contained, and how to use it wisely.

I used AI like a detective throughout the process.

Learning curve engaged.

And a mad fury of curiosity kicked in.

My job was simple: figure out how to make this stupid enough that I could understand what I was looking at and reading.

Me. Myself. Only.

But also provide enough scientific context that an average college student might find it useful for exploratory research.

The thing that always mattered most was also the thing that consumed the most time.

**Time.**

That's my angle here.

The long game.

I started exploring the idea of time snapshots and observation epochs. Then I discovered that moving objects were part of the Space Apps Challenge.

Okay, how do we take time-based snapshots and identify moving objects?

Two weeks before competition day, what could I realistically figure out?

And what's an easy way to display that data?

**You blink them.**

And the blink feature was born.

The first images came from older SPHEREx datasets, and they weren't what I expected at all.

I was expecting colorful, Hubble-style stacked images. Glamour shots, per se.

What I got were black, white, and gray close-ups of stars.

That wasn't quite the visual experience I had imagined.

Then I started thinking about the 102 wavelength channels and how we could incorporate the information they contained into what we were looking at visually.

And the pixel metadata feature was born.

The idea was to let someone click a pixel and inspect the available scientific information associated with that location.

I eventually found wider-field star data instead of just close-ups, and the plan continued evolving.

Because with enough time, things usually reveal themselves.

I researched and integrated JPL trajectory information for known objects to help identify where moving objects should be and which observations might be useful.

Then the static version was built.

Seeing the size of the datasets used for the demonstrations made me understand why an application like this could be useful.

The idea shifted toward time-series exploration.

I wanted to investigate two things:

1. Wavelength information across different observation times.
2. Coverage from multiple astronomical sources for a specific location and timeframe.

That second idea came from my earlier work with WISE, Gaia, and other astronomical datasets.

I already had pipelines from earlier experiments that could potentially be reused.

Mind you, I'm figuring this out as I go.

Then came the failed tests.

And debugging. Lots of debugging.

I had two decent features working and wanted to build more.

But resources were limited, and the amount of testing required was becoming overwhelming.

Nothing was particularly automated in the beginning.

Some workflows were crazy.

I was still doing a significant amount of the testing and verification myself. AI helped make code changes based on findings from my tests and its own.

Between regression testing, scientific verification, and implementation, I genuinely questioned whether the timeline was feasible.

But with time, anything can happen.

**You cannot outwork me.**

That became the motto.

I'm just one person competing against teams.

I didn't believe I had much of a chance.

I'm new to this, and I don't always understand the value of what I've built or what I might be capable of creating with AI-assisted development.

Hence the doubt.

But stubbornness for the win.

The day before the competition, I created a Git checkpoint and started checking whether we had a working, verifiable project lineage.

By the end of the day, we finally passed.

Then I found out the new SPHEREx dataset had been released.

And the loop started all over again.

This time, I caught it.

The new release included 102-channel spectral cube products, opening another way to explore the sky through wavelength.

These cubes combine observations and aren't themselves independent time snapshots. But they provide another valuable layer of scientific information that Cronoscope can explore.

The new data wasn't fully integrated into the original application, so I started testing what could be implemented and verified.

Meanwhile, there was another competition requirement I wasn't prepared for.

**The presentation.**

I'd never made a slide deck before.

Hadn't even used the program until the day of the competition.

Learning curve engaged. Again.

The presentation contains screenshots of the functional application and explains a little more about it.

And now we're here. Letter number two.

More debugging.

More scientific verification.

And an attempt to incorporate the newest dataset into the project.

We come from baby steps.

## Competition Weekend

### Day 1

I had to gather and document data-source URLs, log into my Space Apps account after forgetting my password, upload the required links, and make my initial GitHub publication.

Then came repository testing and getting the static demonstration working directly from GitHub.

I also captured screenshots and built my first presentation.

You have been warned. LOL.

Learning curve engaged.

### Day 2

The focus shifted toward integrating the newly released SPHEREx data.

That meant physical testing, debugging, and verifying that the new functionality actually worked.

The experimental cube reader became a service, and the service became a working browser explorer.

We verified real scientific pixel data, wavelength metadata, and provenance without replacing the original application.

And now I'm writing this second letter while preparing the final GitHub updates.

## Where Does Cronoscope Go From Here?

I don't know how far this project will go or whether it can compete against what more experienced developers and larger teams have created.

My expectations vary.

I just hope someone sees it, likes the direction, understands what I've put together, and sees where I'm trying to take it.

Because I have more ideas.

I'd like to incorporate the pipelines from earlier projects into Cronoscope.

The goal would be to explore overlapping astronomical coverage across different catalogs, wavelengths, distances, and observation times.

I want to investigate:

- How different astronomical surveys overlap across the sky.
- Which wavelengths are available for a particular object or region.
- How observations change across different epochs.
- How to display overlapping catalog coverage in a way people can actually understand.
- How to create RGB visualizations from suitable wavelength data.
- How to verify that displayed pixel information genuinely comes from the correct SPHEREx products.
- How to improve moving-object exploration using scientifically justified comparisons.

And more.

Lots more.

There's still an enormous amount to investigate, test, and verify.

**Time will tell whether we discover anything new.**

For now, Cronoscope is a working foundation for exploring astronomical data, and I intend to keep building on it.

I don't know where this journey ends.

But I'm glad I started it.

Thank you for your consideration.

**Creator of Cronoscope**
