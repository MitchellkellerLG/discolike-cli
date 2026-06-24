# Issue Tracker

## Location

Issues for discolike-cli are tracked on GitHub:

**Repository:** https://github.com/LeadGrowGTM/discolike-cli  
**Issues tab:** https://github.com/LeadGrowGTM/discolike-cli/issues

## What Goes Here

- Bug reports (API errors, CLI crashes, unexpected output)
- Feature requests (new commands, new filter options, output format improvements)
- Documentation gaps
- Test coverage gaps

## Issue Conventions

When filing an issue, include:
1. Command run (with sensitive values masked)
2. Expected behavior
3. Actual behavior + exit code
4. Python version, OS, discolike-cli version (`discolike --version`)

Exit codes serve as a first-pass category:
- Exit 1 = APIError
- Exit 2 = AuthError
- Exit 3 = RateLimitError
- Exit 4 = PlanGateError
- Exit 5 = BudgetExceededError
- Exit 6 = ValidationError
